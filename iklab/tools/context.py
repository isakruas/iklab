from __future__ import annotations

"""Context tools — read-only filesystem access for gathering information."""

import fnmatch
import pathlib

from . import mcp
from .. import sandbox, ignore
from ..config import get_config


@mcp.tool(name="ListDirectory")
def list_directory(path: str = ".") -> str:
    """List files and folders in a directory, respecting ignore rules."""
    p = sandbox.resolve(path)
    if not p.is_dir():
        return f"Error: '{path}' is not a valid directory."
    patterns = ignore.load_ignore_patterns(p)
    lines = []
    for e in sorted(p.iterdir()):
        if ignore.is_ignored(e, p, patterns):
            continue
        if e.is_dir():
            sub = sum(1 for _ in e.iterdir())
            lines.append(f"[DIR]  {e.name}/ ({sub} items)")
        else:
            size = e.stat().st_size
            tag = " [binary]" if ignore.is_binary(e) else ""
            lines.append(f"[FILE] {e.name} ({size}b){tag}")
    return "\n".join(lines) if lines else "(empty or fully ignored)"


@mcp.tool(name="Read")
def read_file(path: str) -> str:
    """Read any file's content. Binary files return a descriptor."""
    p = sandbox.resolve(path)
    if not p.is_file():
        return f"Error: '{path}' is not a valid file."
    return ignore.safe_read(p)


@mcp.tool(name="Glob")
def glob_files(pattern: str, directory: str = ".") -> str:
    """Find files matching a glob pattern, respecting ignore rules."""
    base = sandbox.resolve(directory)
    all_files = ignore.walk_project(base)
    matches = [
        f for f in all_files
        if fnmatch.fnmatch(str(f.relative_to(base)), pattern)
        or fnmatch.fnmatch(f.name, pattern)
    ]
    if not matches:
        return "No files found."
    cfg = get_config()
    return "\n".join(
        str(m.relative_to(sandbox.WORKDIR)) for m in matches[:cfg.max_search_results]
    )


@mcp.tool(name="Grep")
def grep_content(text: str, directory: str = ".", extensions: str = "") -> str:
    """Search for text inside files, respecting ignore rules. Extensions: '.py,.js'"""
    base = sandbox.resolve(directory)
    exts = [e.strip() for e in extensions.split(",") if e.strip()] if extensions else None
    all_files = ignore.walk_project(base)
    results = []
    for fpath in all_files:
        if ignore.is_binary(fpath):
            continue
        if exts and fpath.suffix not in exts:
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            if text in line:
                rel = fpath.relative_to(sandbox.WORKDIR)
                results.append(f"{rel}:{i}: {line.rstrip()}")
        if len(results) >= get_config().max_search_results:
            break
    return "\n".join(results) if results else "No results found."


# ---------------------------------------------------------------------------
# Tool metadata for registry
# ---------------------------------------------------------------------------
TOOL_METADATA = [
    {
        "name": "ListDirectory",
        "category": "context",
        "description": "List files and folders in a directory, respecting ignore rules.",
        "source_module": "tools.context",
    },
    {
        "name": "Read",
        "category": "context",
        "description": "Read any file's content. Binary files return a descriptor.",
        "source_module": "tools.context",
    },
    {
        "name": "Glob",
        "category": "context",
        "description": "Find files matching a glob pattern, respecting ignore rules.",
        "source_module": "tools.context",
    },
    {
        "name": "Grep",
        "category": "context",
        "description": "Search for text inside files, respecting ignore rules.",
        "source_module": "tools.context",
    },
]
