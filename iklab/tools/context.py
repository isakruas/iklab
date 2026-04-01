"""Context tools — read-only filesystem access for gathering information."""

from __future__ import annotations

import fnmatch

from .. import ignore, sandbox
from ..config import get_config
from . import mcp


@mcp.tool(name="List")
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


@mcp.tool(name="ReadLines")
def read_lines(path: str, start: int = 1, end: int = 50) -> str:
    """Read a specific line range from a file. Lines are 1-indexed.

    Use instead of Read for large files to avoid hitting size limits.
    Returns numbered lines like '  42\tcontent'.
    """
    p = sandbox.resolve(path)
    if not p.is_file():
        return f"Error: '{path}' is not a valid file."
    if start < 1:
        start = 1
    if end < start:
        return f"Error: end ({end}) must be >= start ({start})."
    try:
        all_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        return f"Error reading file: {e}"
    total = len(all_lines)
    if start > total:
        return f"Error: file has {total} lines, start={start} is out of range."
    end = min(end, total)
    width = len(str(end))
    selected = []
    for i in range(start - 1, end):
        selected.append(f"{i + 1:>{width}}\t{all_lines[i]}")
    header = f"[{p.relative_to(sandbox.WORKDIR)} — lines {start}-{end} of {total}]"
    return header + "\n" + "\n".join(selected)


@mcp.tool(name="Glob")
def glob_files(pattern: str, directory: str = ".") -> str:
    """Find files matching a glob pattern, respecting ignore rules."""
    base = sandbox.resolve(directory)
    all_files = ignore.walk_project(base)
    matches = [
        f for f in all_files if fnmatch.fnmatch(str(f.relative_to(base)), pattern) or fnmatch.fnmatch(f.name, pattern)
    ]
    if not matches:
        return "No files found."
    cfg = get_config()
    return "\n".join(str(m.relative_to(sandbox.WORKDIR)) for m in matches[: cfg.max_search_results])


@mcp.tool(name="Tree")
def tree(path: str = ".", max_depth: int = 3) -> str:
    """Show recursive directory structure as an indented tree, respecting ignore rules.

    Use instead of List when you need to see the full project layout.
    max_depth controls how deep to recurse (default 3).
    """
    base = sandbox.resolve(path)
    if not base.is_dir():
        return f"Error: '{path}' is not a valid directory."
    cfg = get_config()
    lines: list[str] = [f"{base.relative_to(sandbox.WORKDIR)}/"]
    count = 0
    limit = cfg.max_walk_files

    def _walk(directory, prefix, depth):
        nonlocal count
        if depth > max_depth or count >= limit:
            return
        patterns = ignore.load_ignore_patterns(directory)
        entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        dirs = [e for e in entries if e.is_dir() and not ignore.is_ignored(e, directory, patterns)]
        files = [e for e in entries if e.is_file() and not ignore.is_ignored(e, directory, patterns)]
        items = dirs + files
        for i, entry in enumerate(items):
            if count >= limit:
                lines.append(f"{prefix}... (truncated at {limit} entries)")
                return
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                count += 1
                extension = "    " if is_last else "│   "
                _walk(entry, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")
                count += 1

    _walk(base, "", 1)
    return "\n".join(lines)


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
        "name": "List",
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
        "name": "ReadLines",
        "category": "context",
        "description": "Read a specific line range from a file. Use for large files.",
        "source_module": "tools.context",
    },
    {
        "name": "Glob",
        "category": "context",
        "description": "Find files matching a glob pattern, respecting ignore rules.",
        "source_module": "tools.context",
    },
    {
        "name": "Tree",
        "category": "context",
        "description": "Show recursive directory structure as an indented tree.",
        "source_module": "tools.context",
    },
    {
        "name": "Grep",
        "category": "context",
        "description": "Search for text inside files, respecting ignore rules.",
        "source_module": "tools.context",
    },
]
