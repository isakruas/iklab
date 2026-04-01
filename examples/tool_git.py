"""Example custom tool: Git operations.

Register this tool by importing it in iklab/server.py:
    from .tools import context, planning, execution  # existing
    # Add: import the example tool module if placed in iklab/tools/

Or use it as a standalone reference for building your own tools.
"""

from __future__ import annotations

import subprocess

from iklab.tools import mcp
from iklab import sandbox


@mcp.tool(name="GitStatus")
def git_status() -> str:
    """Show the current git status of the project."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(sandbox.WORKDIR),
        )
        output = result.stdout.strip()
        return output if output else "(clean working tree)"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="GitDiff")
def git_diff(staged: bool = False) -> str:
    """Show git diff (staged or unstaged changes)."""
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--staged")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(sandbox.WORKDIR),
        )
        output = result.stdout.strip()
        return output[:5000] if output else "(no changes)"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="GitLog")
def git_log(count: int = 10) -> str:
    """Show recent git log entries."""
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{count}"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(sandbox.WORKDIR),
        )
        return result.stdout.strip() or "(no commits)"
    except Exception as e:
        return f"Error: {e}"


# Tool metadata for the registry
TOOL_METADATA = [
    {
        "name": "GitStatus",
        "category": "context",
        "description": "Show the current git status of the project.",
        "source_module": "tools.git",
    },
    {
        "name": "GitDiff",
        "category": "context",
        "description": "Show git diff (staged or unstaged changes).",
        "source_module": "tools.git",
    },
    {
        "name": "GitLog",
        "category": "context",
        "description": "Show recent git log entries.",
        "source_module": "tools.git",
    },
]
