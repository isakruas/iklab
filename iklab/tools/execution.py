from __future__ import annotations

"""Execution tools — write files, run commands, think, search web."""

import subprocess

import httpx

from . import mcp
from .. import sandbox, model
from ..config import get_config
from ..prompts import load

AGENT_SYSTEM = load("system")


@mcp.tool(name="Write")
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file."""
    p = sandbox.resolve(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {p.relative_to(sandbox.WORKDIR)} ({len(content)} chars)"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="Bash")
def bash(command: str, timeout: int = 30) -> str:
    """Execute a shell command (sandboxed to working directory)."""
    cfg = get_config()
    cmd_lower = command.lower().strip()
    for blocked in cfg.blocked_commands:
        if blocked in cmd_lower:
            return f"Blocked: dangerous command detected ({blocked})"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=min(timeout, cfg.max_bash_timeout),
            cwd=str(sandbox.WORKDIR),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr
        output += f"\n[exit code: {result.returncode}]"
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"Error: timed out after {timeout}s."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="Think")
async def think(task: str, context: str = "") -> str:
    """Reason about HOW to solve a problem or make a technical decision. Do NOT use for questions about files or state."""
    prompt = f"Task:\n{task}"
    if context:
        prompt += f"\n\nContext:\n{context}"
    return await model.ask(AGENT_SYSTEM, prompt)


@mcp.tool(name="WebSearch")
async def web_search(query: str) -> str:
    """Search the internet via DuckDuckGo."""
    url = "https://html.duckduckgo.com/html/"
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.post(url, data={"q": query})
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        return f"Search error: {e}"

    results = []
    parts = html.split('class="result__a"')
    for part in parts[1:11]:
        title_end = part.find("</a>")
        if title_end == -1:
            continue
        chunk = part[:title_end]
        ts = chunk.rfind(">")
        title = chunk[ts + 1:].strip() if ts != -1 else ""

        hs = part.find('href="')
        href = ""
        if hs != -1:
            he = part.find('"', hs + 6)
            href = part[hs + 6:he]

        snippet = ""
        sm = part.find('class="result__snippet"')
        if sm != -1:
            ss = part.find(">", sm) + 1
            se = part.find("</", ss)
            snippet = part[ss:se].strip().replace("<b>", "").replace("</b>", "")

        if title:
            results.append(f"- {title}\n  {href}\n  {snippet}")

    return "\n\n".join(results) if results else "No results found."


# ---------------------------------------------------------------------------
# Tool metadata for registry
# ---------------------------------------------------------------------------
TOOL_METADATA = [
    {
        "name": "Write",
        "category": "execution",
        "description": "Create or overwrite a file.",
        "source_module": "tools.execution",
    },
    {
        "name": "Bash",
        "category": "execution",
        "description": "Execute a shell command (sandboxed to working directory).",
        "source_module": "tools.execution",
    },
    {
        "name": "Think",
        "category": "execution",
        "description": "Reason about HOW to solve a problem or make a technical decision.",
        "source_module": "tools.execution",
    },
    {
        "name": "WebSearch",
        "category": "execution",
        "description": "Search the internet via DuckDuckGo.",
        "source_module": "tools.execution",
    },
]
