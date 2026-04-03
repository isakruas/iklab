"""Planning tools — deterministic project analysis and context gathering."""

from __future__ import annotations

import collections

from .. import ignore, sandbox
from ..config import get_config
from . import mcp


@mcp.tool(name="AnalyzeProject")
def analyze_project(directory: str = ".") -> str:
    """Return structured project data: tree, file stats, and key file contents.

    Does NOT interpret the data — returns raw facts for the agent to analyze.
    Use this to understand a project before making changes.
    """
    base = sandbox.resolve(directory)
    all_files = ignore.walk_project(base)
    cfg = get_config()

    # --- Section 1: Summary stats ---
    ext_counts: dict[str, int] = collections.Counter()
    total_size = 0
    binary_count = 0
    for fpath in all_files:
        if ignore.is_binary(fpath):
            binary_count += 1
        ext_counts[fpath.suffix or "(no ext)"] += 1
        try:
            total_size += fpath.stat().st_size
        except Exception:
            pass

    top_exts = ext_counts.most_common(10)
    ext_summary = ", ".join(f"{ext}: {n}" for ext, n in top_exts)

    sections: list[str] = []
    sections.append(f"[AnalyzeProject] directory={base.relative_to(sandbox.WORKDIR)}")
    sections.append(f"Total files: {len(all_files)} ({binary_count} binary)")
    sections.append(f"Total size: {total_size:,} bytes")
    sections.append(f"Extensions: {ext_summary}")

    # --- Section 2: Directory tree ---
    sections.append("")
    sections.append("=== PROJECT TREE ===")
    tree_lines: list[str] = []
    for fpath in all_files[: cfg.max_walk_files]:
        rel = fpath.relative_to(base)
        depth = len(rel.parts) - 1
        indent = "  " * depth
        tag = " [binary]" if ignore.is_binary(fpath) else ""
        try:
            size = fpath.stat().st_size
        except Exception:
            size = 0
        tree_lines.append(f"{indent}{fpath.name} ({size}b){tag}")
    sections.append("\n".join(tree_lines))
    if len(all_files) > cfg.max_walk_files:
        sections.append(f"... truncated at {cfg.max_walk_files} entries")

    # --- Section 3: Key file contents ---
    sections.append("")
    sections.append("=== KEY FILES ===")
    budget = cfg.max_read_bytes
    used = 0
    files_shown = 0
    for fpath in all_files:
        if ignore.is_binary(fpath):
            continue
        rel = str(fpath.relative_to(base))
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if len(text) > 3000:
            text = text[:3000] + "\n... [truncated]"
        entry = f"\n--- {rel} ---\n{text}"
        if used + len(entry) > budget:
            remaining = len(all_files) - files_shown
            sections.append(f"\n... {remaining} more files not shown (budget reached)")
            break
        sections.append(entry)
        used += len(entry)
        files_shown += 1

    return "\n".join(sections)


@mcp.tool(name="PlanTask")
def plan_task(task: str, directory: str = ".") -> str:
    """Return project context relevant to a task, so the agent can plan next steps.

    Does NOT generate a plan — returns the file list and key contents
    so the agent model itself can decide what to do.
    """
    base = sandbox.resolve(directory)
    all_files = ignore.walk_project(base)
    cfg = get_config()

    sections: list[str] = []
    sections.append(f"[PlanTask] task={task!r}")
    sections.append(f"directory={base.relative_to(sandbox.WORKDIR)}")
    sections.append(f"Total files: {len(all_files)}")

    # --- File list ---
    sections.append("")
    sections.append("=== FILE LIST ===")
    file_list = "\n".join(str(f.relative_to(base)) for f in all_files[:200])
    if len(all_files) > 200:
        file_list += f"\n... ({len(all_files)} files total)"
    sections.append(file_list)

    # --- Key file contents ---
    sections.append("")
    sections.append("=== KEY FILES ===")
    budget = min(cfg.max_read_bytes, 100_000)
    used = 0
    for fpath in all_files:
        if ignore.is_binary(fpath):
            continue
        rel = str(fpath.relative_to(base))
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if len(text) > 2000:
            text = text[:2000] + "\n... [truncated]"
        entry = f"\n--- {rel} ---\n{text}"
        if used + len(entry) > budget:
            sections.append("\n... more files not shown (budget reached)")
            break
        sections.append(entry)
        used += len(entry)

    # --- Available tools reminder ---
    sections.append("")
    sections.append("=== AVAILABLE TOOLS ===")
    sections.append(
        "List, Read, ReadLines, Glob, Tree, Grep, "
        "Write, WriteLines, Edit, Patch, Move, Copy, Delete, Undo, "
        "Shell, WebSearch, WebFetch"
    )

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Tool metadata for registry
# ---------------------------------------------------------------------------
TOOL_METADATA = [
    {
        "name": "AnalyzeProject",
        "category": "planning",
        "description": "Return project tree, file stats, and key file contents. Use to understand a project.",
        "source_module": "tools.planning",
    },
    {
        "name": "PlanTask",
        "category": "planning",
        "description": "Return project context for a task: file list and key contents. You decide the plan.",
        "source_module": "tools.planning",
    },
]
