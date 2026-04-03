from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import sys
import uuid

import httpx
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from . import sandbox
from .bootstrap import BootstrapGraph, build_bootstrap_graph
from .config import get_config
from .cost_tracker import CostTracker
from .history import HistoryLog
from .model import ask, chat
from .models import AgentConfig, SessionInfo, TurnResult
from .permissions import ToolApprover, ToolPermissionContext
from .prompt_builder import build_system_prompt
from .query_engine import QueryEngine, QueryEngineConfig
from .session_store import load_session, save_session
from .tool_pool import ToolPool, assemble_tool_pool
from .tool_registry import ToolRegistry, build_tool_registry
from .transcript import Transcript

R = "\033[0m"
B = "\033[1m"
D = "\033[2m"
C = "\033[36m"
G = "\033[32m"
Y = "\033[33m"
M = "\033[35m"
RED = "\033[31m"


def mcp_tools_to_openai(mcp_tools: list) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema or {"type": "object", "properties": {}},
            },
        }
        for t in mcp_tools
    ]


class Agent:
    def __init__(
        self,
        session: ClientSession,
        tools: list,
        cfg: AgentConfig | None = None,
        *,
        simple_mode: bool = False,
        permission_context: ToolPermissionContext | None = None,
        max_turns: int = 8,
        session_id: str | None = None,
        approver: ToolApprover | None = None,
    ):
        self.session = session
        self.tools = tools
        self.cfg = cfg or get_config()

        # --- registry & pool ---
        self.registry: ToolRegistry = build_tool_registry()
        self.tool_pool: ToolPool = assemble_tool_pool(
            self.registry,
            simple_mode=simple_mode,
            permission_context=permission_context,
            phase="execution",
        )

        # --- permission approver ---
        self.approver: ToolApprover = approver or ToolApprover()

        # --- prompt ---
        self.current_expert_protocol = ""

        # --- loop detection ---
        self._recent_calls: list[str] = []  # last N "name:args" signatures
        self._max_repeats = 3  # break loop after this many identical consecutive calls
        self._blocked_sigs: set[str] = set()  # blocked call signatures (cleared on different call)
        self._consecutive_blocks: int = 0  # count consecutive blocked turns
        self._max_consecutive_blocks: int = 3  # stop after this many consecutive blocks
        self._protocol_hint_sent: bool = False  # only send protocol reminder once
        self._tool_hint_sent: bool = False  # only send tool usage hint once per task

        # --- session state ---
        self.transcript = Transcript()
        self.history = HistoryLog()
        self.cost_tracker = CostTracker()
        self.session_id = session_id or uuid.uuid4().hex[:12]

        # --- query engine ---
        self.query_engine = QueryEngine(
            config=QueryEngineConfig(max_turns=max_turns),
            transcript=self.transcript,
            cost_tracker=self.cost_tracker,
            history=self.history,
        )

        # --- bootstrap ---
        self.bootstrap: BootstrapGraph = build_bootstrap_graph()

    def _build_system_prompt(self) -> str:
        return build_system_prompt(
            cfg=self.cfg,
            tool_pool=self.tool_pool,
            expert_protocol=self.current_expert_protocol,
        )

    async def _compact(self) -> None:
        """Compact the transcript by asking the model to summarize old entries.

        Uses the summarize skill format: the model receives the old messages
        and produces a structured summary (TASK, PROGRESS, FILES CHANGED,
        DECISIONS, REMAINING). This replaces the old entries with a single
        summary message, keeping recent context intact.
        """
        if not self.query_engine.should_compact():
            return

        entries = self.transcript.entries
        keep_recent = 20  # last 20 messages stay intact (covers ~7 tool turns)

        if len(entries) <= keep_recent:
            return

        # 1. Find original task (first user message)
        original_task = None
        for entry in entries:
            if entry.get("role") == "user":
                original_task = entry
                break

        # 2. Split: old entries (to compress) vs recent (to keep intact)
        old_entries = entries[:-keep_recent]
        recent_entries = entries[-keep_recent:]

        # 3. Build a condensed text of old entries for the model to summarize
        condensed_lines: list[str] = []
        for entry in old_entries:
            role = entry.get("role", "")
            content = entry.get("content", "")
            if role == "tool":
                # Only first line of tool outputs (they can be huge)
                first_line = content.split("\n", 1)[0][:200]
                condensed_lines.append(f"[tool] {first_line}")
            elif role == "assistant" and content:
                if "<EXPERT_PROTOCOL>" in content:
                    continue  # handled separately
                condensed_lines.append(f"[assistant] {content[:300]}")
            elif role == "user":
                condensed_lines.append(f"[user] {content[:200]}")
        condensed_text = "\n".join(condensed_lines)

        # 4. Ask the model to summarize using the skill format
        summarize_prompt = (
            "You are a summarization assistant. "
            "Summarize the following conversation history into a structured format.\n"
            "Rules:\n"
            "- Keep under 300 words.\n"
            "- Focus on FACTS and ACTIONS only.\n"
            "- Preserve file paths, variable names, and technical specifics.\n"
            "- Drop intermediate errors that were already resolved.\n"
            "- Drop verbose tool outputs — reference by path instead.\n\n"
            "Output format:\n"
            "TASK: <one-line description of the user's goal>\n"
            "PROGRESS:\n- <completed step>\n"
            "FILES CHANGED:\n- <path>: <what changed>\n"
            "DECISIONS:\n- <key decision and rationale>\n"
            "REMAINING:\n- <next step>\n"
        )

        print(f"{D}[COMPACT] Summarizing {len(old_entries)} old entries...{R}")
        summary_text = ""
        attempt = 0
        while not summary_text:
            if self._interrupted:
                print(f"{Y}[COMPACT] Interrupted by user. Keeping transcript as-is.{R}")
                return
            attempt += 1
            try:
                result = await ask(summarize_prompt, condensed_text)
                result = result.strip()
                # Strip markdown fences the model might add
                if result.startswith("```"):
                    lines = result.splitlines()
                    lines = [line for line in lines if not line.startswith("```")]
                    result = "\n".join(lines).strip()
                if result:
                    summary_text = result
            except (asyncio.CancelledError, httpx.ReadError, httpx.ConnectError):
                if self._interrupted:
                    print(f"{Y}[COMPACT] Interrupted by user. Keeping transcript as-is.{R}")
                    return
                raise
            except Exception as e:
                if self._interrupted:
                    print(f"{Y}[COMPACT] Interrupted by user. Keeping transcript as-is.{R}")
                    return
                print(f"{Y}[COMPACT] Attempt {attempt} failed: {e}. Retrying in 2s...{R}")
                await asyncio.sleep(2)

        # 5. Rebuild transcript: original task + summary + expert protocol + recent
        compacted: list[dict] = []

        if original_task:
            if original_task not in recent_entries:
                compacted.append(original_task)

        compacted.append(
            {
                "role": "assistant",
                "content": f"<HISTORY_SUMMARY>\n{summary_text}\n</HISTORY_SUMMARY>",
            }
        )

        if self.current_expert_protocol:
            compacted.append(
                {
                    "role": "assistant",
                    "content": f"<EXPERT_PROTOCOL>{self.current_expert_protocol}</EXPERT_PROTOCOL>",
                }
            )

        compacted.extend(recent_entries)

        before = len(entries)
        self.transcript.entries[:] = compacted
        after = len(compacted)
        self.history.add("compact", f"Compacted transcript {before} -> {after} entries (model-summarized)")
        print(f"{D}[COMPACT] {before} -> {after} entries{R}")

    async def _force_compact(self) -> None:
        """Force compaction regardless of threshold (used by /summarize command)."""
        entries = self.transcript.entries
        if not entries:
            return
        original_threshold = self.query_engine.config.compact_after_entries
        try:
            object.__setattr__(self.query_engine.config, "compact_after_entries", 0)
            if len(entries) > 2:
                await self._compact()
        finally:
            object.__setattr__(self.query_engine.config, "compact_after_entries", original_threshold)

    # Flag set by SIGINT handler to signal the loop to pause
    _interrupted: bool = False

    def _handle_sigint(self, signum, frame):
        """Signal handler for Ctrl+C — sets flag instead of raising."""
        self._interrupted = True
        print(f"\n{Y}{B}[INTERRUPTED]{R} {D}Finishing current step, then pausing...{R}")

    async def _generate_expert_protocol(self, user_input: str) -> None:
        """Generate expert protocol via a dedicated model call (no tools).

        Granite in tool-calling mode cannot output text alongside tool calls,
        so we make a separate call without tools to get the protocol.
        """
        if self.current_expert_protocol:
            return  # already set

        prompt = (
            "You are an expert protocol generator. "
            "Given the user's task, output ONLY an <EXPERT_PROTOCOL> block. "
            "No explanation, no tool calls, just the protocol.\n\n"
            "Format:\n"
            "<EXPERT_PROTOCOL>\n"
            "[MODE: EXPERT_TYPE]\n"
            "[STACK: technologies]\n"
            "[RULES:\n1. rule\n2. rule\n]\n"
            "</EXPERT_PROTOCOL>"
        )
        try:
            result = await ask(prompt, user_input)
            result = result.strip()
            # Extract protocol from response
            match = re.search(r"<EXPERT_PROTOCOL>(.*?)</EXPERT_PROTOCOL>", result, re.DOTALL)
            if not match:
                match = re.search(r"<EXPERT_PROTOCOL>\s*(.*)", result, re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                extracted = re.sub(r"```(?:json)?\s*", "", extracted)
                extracted = re.sub(r"```\s*$", "", extracted)
                extracted = extracted.strip()
                if extracted:
                    self.current_expert_protocol = extracted
                    self._protocol_hint_sent = True
                    self.history.add("protocol_update", "Expert protocol generated")
                    print(f"{C}{B}[ORCHESTRATION] Expert Protocol Generated.{R}")
        except Exception as e:
            print(f"{Y}[ORCHESTRATION] Could not generate protocol: {e}{R}")

    async def chat_loop(self, user_input: str) -> TurnResult:
        self.transcript.append({"role": "user", "content": user_input})
        self.history.add("user_input", user_input[:120])
        self._interrupted = False

        # Generate expert protocol before entering the loop
        await self._generate_expert_protocol(user_input)

        # Install SIGINT handler to catch Ctrl+C gracefully
        prev_handler = signal.signal(signal.SIGINT, self._handle_sigint)

        last_content = ""
        total_input = 0
        total_output = 0
        tool_call_records: list[dict] = []

        try:
            return await self._chat_loop_inner(last_content, total_input, total_output, tool_call_records)
        finally:
            # Restore original signal handler so input() works normally
            signal.signal(signal.SIGINT, prev_handler)

    async def _chat_loop_inner(
        self,
        last_content: str,
        total_input: int,
        total_output: int,
        tool_call_records: list[dict],
    ) -> TurnResult:
        while True:
            # Check if user interrupted (Ctrl+C)
            if self._interrupted:
                print(f"{Y}{B}[PAUSED]{R} {D}Execution paused. Type your correction below.{R}")
                self.history.add("interrupted", "User interrupted execution")
                break

            # Budget / turn check
            stop, reason = self.query_engine.should_stop()
            if stop:
                print(f"{Y}[ENGINE] Stopping: {reason}{R}")
                self.history.add("engine_stop", reason)
                break

            await self._compact()

            messages = [{"role": "system", "content": self._build_system_prompt()}] + self.transcript.entries
            try:
                data = await chat(messages, self.tools)
            except (asyncio.CancelledError, httpx.ReadError, httpx.ConnectError):
                # asyncio cancels the task on SIGINT; httpx may raise on broken connection
                self._interrupted = True
                print(f"\n{Y}{B}[PAUSED]{R} {D}Execution paused. Type your correction below.{R}")
                self.history.add("interrupted", "User interrupted during model call")
                break

            if self._interrupted:
                # Signal arrived while awaiting but didn't raise
                print(f"{Y}{B}[PAUSED]{R} {D}Execution paused. Type your correction below.{R}")
                self.history.add("interrupted", "User interrupted after model call")
                break

            message = data["choices"][0]["message"]
            content = message.get("content", "")

            # Track token usage
            usage = data.get("usage", {})
            in_tok = usage.get("prompt_tokens", 0)
            out_tok = usage.get("completion_tokens", 0)
            total_input += in_tok
            total_output += out_tok

            # Extract expert protocol
            if "<EXPERT_PROTOCOL>" in content:
                # Try with closing tag first, then fallback to everything after opening tag
                match = re.search(r"<EXPERT_PROTOCOL>(.*?)</EXPERT_PROTOCOL>", content, re.DOTALL)
                if not match:
                    match = re.search(r"<EXPERT_PROTOCOL>\s*(.*)", content, re.DOTALL)
                if match:
                    extracted = match.group(1).strip()
                    # Clean markdown artifacts (**, ```, etc.)
                    extracted = re.sub(r"^\*\*.*?\*\*\s*", "", extracted)
                    extracted = re.sub(r"```(?:json)?\s*", "", extracted)
                    extracted = re.sub(r"```\s*$", "", extracted)
                    extracted = extracted.strip()
                    if extracted:
                        self.current_expert_protocol = extracted
                        self.history.add("protocol_update", "Expert protocol updated")
                        print(f"{C}{B}[ORCHESTRATION] Meta-Protocol Updated.{R}")

            if content:
                print(f"{G}{content}{R}\n")

            self.transcript.append(message)
            tool_calls = message.get("tool_calls")

            # Force tool usage when model outputs code instead of using tools (once per task)
            if not tool_calls and not self._tool_hint_sent and "install" in content.lower():
                self._tool_hint_sent = True
                print(f"{Y}[HINT] Model trying to chat. Forcing tool usage...{R}")
                self.transcript.append(
                    {
                        "role": "user",
                        "content": (
                            "STRICT_HINT: Do not explain."
                            " Use [Write] or [Shell] tools to EXECUTE the code/command shown above now."
                        ),
                    }
                )
                turn = TurnResult(
                    content=content,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    stop_reason="hint",
                )
                self.query_engine.record_turn(turn)
                continue

            if not tool_calls:
                last_content = content
                # Record final turn
                turn = TurnResult(
                    content=content,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    stop_reason="end_turn",
                )
                self.query_engine.record_turn(turn)
                break

            # --- Loop detection ---
            call_sigs = []
            for tc in tool_calls:
                try:
                    args_raw = tc["function"]["arguments"]
                except KeyError:
                    args_raw = ""
                call_sigs.append(f"{tc['function']['name']}:{args_raw}")

            current_sig = "|".join(call_sigs)

            # If the model is doing something DIFFERENT, clear the block
            # (e.g., it fixed a file and now wants to re-run the test)
            if current_sig not in self._blocked_sigs and self._blocked_sigs:
                self._blocked_sigs.clear()
                self._consecutive_blocks = 0

            # Check 1: is this call currently blocked?
            if current_sig in self._blocked_sigs:
                self._consecutive_blocks += 1
                if self._consecutive_blocks >= self._max_consecutive_blocks:
                    print(f"{RED}[LOOP] Model stuck after {self._consecutive_blocks} blocked attempts. Stopping.{R}")
                    self.history.add("loop_stuck", f"Stopped after {self._consecutive_blocks} consecutive blocks")
                    for tc in tool_calls:
                        self.transcript.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": "STOPPED: Too many consecutive blocked attempts.",
                            }
                        )
                    break
                print(f"{RED}[LOOP] Blocked — do something different first.{R}")
                self.history.add("loop_blocked", current_sig[:80])
                for tc in tool_calls:
                    self.transcript.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": (
                                "BLOCKED: This call failed multiple times in a row. "
                                "You must do something DIFFERENT first (fix the file, "
                                "read the error, change the approach), then you can retry."
                            ),
                        }
                    )
                    tool_call_records.append(tc)
                turn = TurnResult(
                    content=content,
                    tool_calls=tuple(tool_call_records),
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    stop_reason="loop_blocked",
                )
                self.query_engine.record_turn(turn)
                continue

            # Check 2: repetition detection (3 identical consecutive calls)
            self._recent_calls.append(current_sig)
            if len(self._recent_calls) > self._max_repeats:
                self._recent_calls = self._recent_calls[-self._max_repeats :]

            if len(self._recent_calls) >= self._max_repeats and len(set(self._recent_calls[-self._max_repeats :])) == 1:
                msg = f"Detected {self._max_repeats} identical calls. Blocking."
                print(f"{RED}[LOOP] {msg}{R}")
                self.history.add("loop_detected", current_sig[:80])
                # Block this signature until the model does something different
                self._blocked_sigs.add(current_sig)
                self._recent_calls.clear()
                for tc in tool_calls:
                    self.transcript.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": (
                                "LOOP DETECTED: You called this exact tool with the same arguments "
                                f"{self._max_repeats} times in a row. This call is BLOCKED until "
                                "you do something different first. Options:\n"
                                "1. Read the error output and fix the root cause with Edit or Write\n"
                                "2. Read the file to understand what's wrong\n"
                                "3. Try a different command or tool\n"
                                "After doing something different, you can retry this call."
                            ),
                        }
                    )
                    tool_call_records.append(tc)
                turn = TurnResult(
                    content=content,
                    tool_calls=tuple(tool_call_records),
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    stop_reason="loop_break",
                )
                self.query_engine.record_turn(turn)
                continue

            # Sequential tool execution with permission check
            for tc in tool_calls:
                # Check interrupt before each tool
                if self._interrupted:
                    # Provide dummy results for remaining tool calls so transcript stays valid
                    self.transcript.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": "[INTERRUPTED] User paused execution before this tool ran.",
                        }
                    )
                    tool_call_records.append(tc)
                    continue

                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    fn_args = {}

                args_str = ", ".join(f"{k}={repr(v)[:80]}" for k, v in fn_args.items())
                print(f"  {Y}{B}[Tool]{R} {M}{fn_name}{R}{D}({args_str}){R}")

                # Permission gate
                if not self.approver.approve(fn_name, args_str):
                    output = f"Denied: user refused permission for {fn_name}"
                    print(f"       {RED}-> {output}{R}")
                    self.transcript.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": output,
                        }
                    )
                    self.history.add("tool_denied", fn_name)
                    tool_call_records.append(tc)
                    continue

                try:
                    result = await self.session.call_tool(fn_name, fn_args)
                    output = "\n".join(b.text for b in result.content if hasattr(b, "text"))
                except Exception as e:
                    output = f"Error: {e}"

                print(f"       {D}-> {output[:200].replace(chr(10), ' ')}...{R}")
                self.transcript.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": output,
                    }
                )
                self.history.add("tool_call", f"{fn_name} -> {output[:80]}")
                tool_call_records.append(tc)

            # Record a turn for the tool-calling round
            turn = TurnResult(
                content=content,
                tool_calls=tuple(tool_call_records),
                input_tokens=in_tok,
                output_tokens=out_tok,
                stop_reason="tool_use",
            )
            self.query_engine.record_turn(turn)

        return TurnResult(
            content=last_content,
            tool_calls=tuple(tool_call_records),
            input_tokens=total_input,
            output_tokens=total_output,
            stop_reason="end_turn",
        )

    def build_session_info(self) -> SessionInfo:
        usage = self.cost_tracker.summary()
        return SessionInfo(
            session_id=self.session_id,
            messages=self.transcript.replay(),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "iklab.server"],
        env={**dict(os.environ), "IKLAB_WORKDIR": str(sandbox.WORKDIR)},
    )


async def run_interactive(
    *,
    simple_mode: bool = False,
    permission_context: ToolPermissionContext | None = None,
    max_turns: int = 8,
    session_id: str | None = None,
    show_history: bool = False,
    approver: ToolApprover | None = None,
) -> None:
    print(f"{C}{B}IKLab Agent{R} {D}(type /help for commands){R}\n")

    # Bootstrap
    bootstrap = build_bootstrap_graph()
    print(f"{D}Bootstrap: {' -> '.join(bootstrap.stages)}{R}\n")

    async with stdio_client(_server_params()) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = mcp_tools_to_openai(tools_result.tools)
            print(f"{D}{len(tools_result.tools)} tools loaded.{R}\n")

            # Restore session if requested
            transcript_entries: list[dict] = []
            if session_id:
                try:
                    prev = load_session(session_id)
                    transcript_entries = list(prev.messages)
                    print(f"{D}Restored session {session_id} ({len(transcript_entries)} messages).{R}\n")
                except FileNotFoundError:
                    print(f"{Y}Session {session_id} not found, starting fresh.{R}\n")
                    session_id = None

            agent = Agent(
                session,
                tools,
                simple_mode=simple_mode,
                permission_context=permission_context,
                max_turns=max_turns,
                session_id=session_id,
                approver=approver or ToolApprover(),
            )
            # Reload transcript from previous session
            for entry in transcript_entries:
                agent.transcript.append(entry)

            if simple_mode:
                print(f"{D}Simple mode: {', '.join(agent.tool_pool.names())}{R}\n")

            while True:
                try:
                    task = input(f"{B}> {R}").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not task or task.lower() in ("exit", "quit", "q"):
                    break

                # --- Slash commands ---
                cmd = task.lower()

                if cmd == "/help":
                    print(
                        f"\n{C}{B}Commands:{R}\n"
                        f"  {G}Ctrl+C{R}      — Pause execution and give a new instruction\n"
                        f"  {G}/prompt{R}     — Export the full system prompt being sent to the model\n"
                        f"  {G}/protocol{R}   — Show the active expert protocol\n"
                        f"  {G}/summarize{R}  — Summarize and compact the conversation history\n"
                        f"  {G}/reset{R}      — Reset session (clear transcript and state)\n"
                        f"  {G}/stop{R}       — Save session and quit\n"
                        f"  {G}/history{R}    — Show action history log\n"
                        f"  {G}exit{R}        — Quit the agent\n"
                    )
                    continue

                if cmd == "/prompt":
                    full_prompt = agent._build_system_prompt()
                    print(f"\n{D}{'=' * 60}{R}")
                    print(full_prompt)
                    print(f"{D}{'=' * 60}{R}")
                    print(f"{D}({len(full_prompt)} chars){R}\n")
                    continue

                if cmd == "/protocol":
                    ep = agent.current_expert_protocol
                    if ep:
                        print(f"\n{C}{B}Active Expert Protocol:{R}")
                        print(f"{D}{'=' * 60}{R}")
                        print(ep)
                        print(f"{D}{'=' * 60}{R}\n")
                    else:
                        print(f"{Y}No expert protocol active.{R}\n")
                    continue

                if cmd == "/summarize":
                    before = len(agent.transcript.entries)
                    if before == 0:
                        print(f"{Y}Nothing to summarize — transcript is empty.{R}\n")
                        continue
                    # Clear interrupt flag so compaction can proceed after Ctrl+C
                    agent._interrupted = False
                    # Force compaction regardless of threshold
                    await agent._force_compact()
                    after = len(agent.transcript.entries)
                    if after >= before:
                        print(f"{Y}Compaction did not reduce entries ({before}). Try again.{R}\n")
                        continue
                    # Clear accumulated state so summarized context starts fresh
                    agent.query_engine.reset()
                    agent._recent_calls.clear()
                    agent._blocked_sigs.clear()
                    agent._consecutive_blocks = 0
                    agent.current_expert_protocol = ""
                    agent._protocol_hint_sent = False
                    agent._tool_hint_sent = False
                    agent.history.clear()
                    agent.history.add("summarize", f"Compacted {before} → {after} entries")
                    print(f"{G}Summarized: {before} → {after} entries. State cleared.{R}\n")
                    continue

                if cmd == "/reset":
                    agent.transcript.entries.clear()
                    agent.current_expert_protocol = ""
                    agent._protocol_hint_sent = False
                    agent._tool_hint_sent = False
                    agent._recent_calls.clear()
                    agent._blocked_sigs.clear()
                    agent._consecutive_blocks = 0
                    agent.query_engine.reset()
                    agent.history.add("reset", "Session reset by user")
                    print(f"{G}Session reset. Transcript and state cleared.{R}\n")
                    continue

                if cmd == "/stop":
                    info = agent.build_session_info()
                    if info.messages:
                        path = save_session(info)
                        print(f"{G}Session saved: {path}{R}")
                    print(f"{Y}Processing stopped.{R}\n")
                    break

                if cmd == "/history":
                    print(f"\n{agent.history.as_markdown()}\n")
                    continue

                await agent.chat_loop(task)

            # Show history if requested
            if show_history:
                print(f"\n{agent.history.as_markdown()}")

            # Persist session on exit
            info = agent.build_session_info()
            if info.messages:
                path = save_session(info)
                print(f"{D}Session saved: {path}{R}")


async def run_single_task(
    task: str,
    *,
    simple_mode: bool = False,
    permission_context: ToolPermissionContext | None = None,
    max_turns: int = 8,
    approver: ToolApprover | None = None,
) -> None:
    async with stdio_client(_server_params()) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = mcp_tools_to_openai(tools_result.tools)
            agent = Agent(
                session,
                tools,
                simple_mode=simple_mode,
                permission_context=permission_context,
                max_turns=max_turns,
                approver=approver or ToolApprover(),
            )
            await agent.chat_loop(task)

            # Persist session
            info = agent.build_session_info()
            if info.messages:
                save_session(info)
