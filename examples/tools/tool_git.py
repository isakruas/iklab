"""Custom tool: Git operations.

Provides read-only Git tools that let the agent inspect repository state —
status, diff, log, and blame — without modifying the working tree.

Usage:
    1. Point your settings.json tool_paths to this directory:
       {"tool_paths": ["./tools", "iklab.tools"]}

    2. Or copy this file into iklab/tools/ and import it in server.py:
       from .tools import git  # noqa: F401
"""

from __future__ import annotations

import subprocess
from typing import Optional

from iklab import sandbox
from iklab.tools import mcp


def _git(*args: str, timeout: int = 10) -> str:
    """Run a git command inside the sandbox workdir and return its output."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(sandbox.WORKDIR),
        )
        output = (result.stdout + result.stderr).strip()
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out."
    except FileNotFoundError:
        return "Error: git is not installed."
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(name="GitStatus")
def git_status() -> str:
    """Show the working-tree status (staged, unstaged, and untracked files).

    Returns a compact summary similar to `git status --short --branch`.
    """
    return _git("status", "--short", "--branch")


@mcp.tool(name="GitDiff")
def git_diff(staged: bool = False, path: Optional[str] = None) -> str:
    """Show line-level changes in the working tree or staging area.

    Args:
        staged: If True, show only staged (--cached) changes.
        path:   Optional file path to restrict the diff to a single file.
    """
    args = ["diff"]
    if staged:
        args.append("--cached")
    if path:
        args.extend(["--", path])
    output = _git(*args, timeout=15)
    if len(output) > 8000:
        return output[:8000] + "\n... (truncated)"
    return output


@mcp.tool(name="GitLog")
def git_log(count: int = 15, path: Optional[str] = None) -> str:
    """Show recent commit history.

    Args:
        count: Number of commits to show (default 15, max 50).
        path:  Optional file path to show history for a single file.
    """
    n = min(max(count, 1), 50)
    args = ["log", "--oneline", "--decorate", f"-{n}"]
    if path:
        args.extend(["--", path])
    return _git(*args)


@mcp.tool(name="GitBlame")
def git_blame(path: str, line_start: int = 1, line_end: int = 50) -> str:
    """Show per-line authorship for a file (git blame).

    Args:
        path:       File path relative to the repository root.
        line_start: First line to annotate (1-based, default 1).
        line_end:   Last line to annotate (default 50).
    """
    start = max(line_start, 1)
    end = max(line_end, start)
    output = _git("blame", f"-L{start},{end}", "--date=short", "--", path, timeout=15)
    if len(output) > 8000:
        return output[:8000] + "\n... (truncated)"
    return output


# ---------------------------------------------------------------------------
# Tool metadata — required so the tool registry can discover and categorize
# these tools when this directory is listed in tool_paths.
# ---------------------------------------------------------------------------

TOOL_METADATA = [
    {
        "name": "GitStatus",
        "category": "context",
        "description": "Show the working-tree status (staged, unstaged, and untracked files).",
        "source_module": "tools.tool_git",
    },
    {
        "name": "GitDiff",
        "category": "context",
        "description": "Show line-level changes in the working tree or staging area.",
        "source_module": "tools.tool_git",
    },
    {
        "name": "GitLog",
        "category": "context",
        "description": "Show recent commit history.",
        "source_module": "tools.tool_git",
    },
    {
        "name": "GitBlame",
        "category": "context",
        "description": "Show per-line authorship for a file.",
        "source_module": "tools.tool_git",
    },
]
