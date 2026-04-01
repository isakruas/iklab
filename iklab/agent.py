from __future__ import annotations

import json
import os
import re
import sys
import uuid

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

    async def _summarize(self) -> None:
        if not self.query_engine.should_compact():
            return
        try:
            summary_prompt = "Summarize the technical state and current Expert Protocol. Prune history while keeping facts."
            summary = await ask(
                self._build_system_prompt(),
                f"History: {json.dumps(self.transcript.entries)}\n\n{summary_prompt}",
            )
            memo = {"role": "assistant", "content": f"<MEMO: {summary}>"}
            last_two = self.transcript.entries[-2:]
            self.transcript.entries[:] = [memo] + last_two
            self.history.add("summarize", f"Compacted transcript to {len(self.transcript)} entries")
        except Exception as exc:
            # Summarization failed (timeout, network, etc.) — fall back to simple compaction
            print(f"{Y}[WARN] Summarize failed ({type(exc).__name__}), compacting locally.{R}")
            self.transcript.compact(keep_last=10)
            self.history.add("summarize_fallback", f"Local compact after error: {exc}")

    async def chat_loop(self, user_input: str) -> TurnResult:
        self.transcript.append({"role": "user", "content": user_input})
        self.history.add("user_input", user_input[:120])

        last_content = ""
        total_input = 0
        total_output = 0
        tool_call_records: list[dict] = []

        while True:
            # Budget / turn check
            stop, reason = self.query_engine.should_stop()
            if stop:
                print(f"{Y}[ENGINE] Stopping: {reason}{R}")
                self.history.add("engine_stop", reason)
                break

            await self._summarize()

            messages = [{"role": "system", "content": self._build_system_prompt()}] + self.transcript.entries
            data = await chat(messages, self.tools)
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
                print(f"{C}{B}[ORCHESTRATION] Meta-Protocol Updated.{R}")
                match = re.search(r"<EXPERT_PROTOCOL>(.*?)</EXPERT_PROTOCOL>", content, re.DOTALL)
                if match:
                    self.current_expert_protocol = match.group(1).strip()
                    self.history.add("protocol_update", "Expert protocol updated")

            if content:
                print(f"{G}{content}{R}\n")

            self.transcript.append(message)
            tool_calls = message.get("tool_calls")

            # Force tool usage when model tries to chat instead of act
            if not tool_calls and ("```" in content or "install" in content.lower()):
                print(f"{Y}[HINT] Model trying to chat. Forcing tool usage...{R}")
                self.transcript.append({
                    "role": "user",
                    "content": "STRICT_HINT: Do not explain. Use [Write] or [Bash] tools to EXECUTE the code/command shown above now.",
                })
                # Record a turn for the hint round
                turn = TurnResult(content=content, input_tokens=in_tok, output_tokens=out_tok, stop_reason="hint")
                self.query_engine.record_turn(turn)
                continue

            if not tool_calls:
                last_content = content
                # Record final turn
                turn = TurnResult(content=content, input_tokens=in_tok, output_tokens=out_tok, stop_reason="end_turn")
                self.query_engine.record_turn(turn)
                break

            # Sequential tool execution with permission check
            for tc in tool_calls:
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
                    self.transcript.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": output,
                    })
                    self.history.add("tool_denied", fn_name)
                    tool_call_records.append(tc)
                    continue

                try:
                    result = await self.session.call_tool(fn_name, fn_args)
                    output = "\n".join(b.text for b in result.content if hasattr(b, "text"))
                except Exception as e:
                    output = f"Error: {e}"

                print(f"       {D}-> {output[:200].replace(chr(10), ' ')}...{R}")
                self.transcript.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": output,
                })
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
    print(f"{C}{B}IKLab Agent{R} {D}(type 'exit' to quit){R}\n")

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
