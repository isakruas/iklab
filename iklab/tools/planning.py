from __future__ import annotations

"""Planning tools — use the model to analyze projects and create execution plans."""

import pathlib

from . import mcp
from .. import sandbox, ignore, model
from ..config import get_config
from ..prompts import load

AGENT_SYSTEM = load("system")


@mcp.tool(name="AnalyzeProject")
async def analyze_project(directory: str = ".") -> str:
    """Deep analysis of the project: structure, stack, purpose, architecture."""
    base = sandbox.resolve(directory)
    all_files = ignore.walk_project(base)

    tree_lines = []
    for fpath in all_files:
        rel = fpath.relative_to(base)
        depth = len(rel.parts) - 1
        indent = "  " * depth
        tag = " [binary]" if ignore.is_binary(fpath) else ""
        size = fpath.stat().st_size if fpath.exists() else 0
        tree_lines.append(f"{indent}{fpath.name} ({size}b){tag}")
    tree = "\n".join(tree_lines[:get_config().max_walk_files])

    key_content = ""
    budget = 15_000
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
        entry = f"\n--- {rel} ---\n{text}\n"
        if len(key_content) + len(entry) > budget:
            key_content += f"\n... [{len(all_files)} files total, truncated]\n"
            break
        key_content += entry

    prompt = f"Project tree ({len(all_files)} files):\n{tree}\n\nFile contents:\n{key_content}"
    return await model.ask(AGENT_SYSTEM, f"Analyze this project completely:\n\n{prompt}")


@mcp.tool(name="PlanTask")
async def plan_task(task: str, directory: str = ".") -> str:
    """Create a step-by-step execution plan for a task."""
    base = sandbox.resolve(directory)
    all_files = ignore.walk_project(base)

    file_list = "\n".join(str(f.relative_to(base)) for f in all_files[:100])
    if len(all_files) > 100:
        file_list += f"\n... ({len(all_files)} files total)"

    context = ""
    budget = 10_000
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
        entry = f"\n--- {rel} ---\n{text}\n"
        if len(context) + len(entry) > budget:
            break
        context += entry

    prompt = f"""Task: {task}

Project files:
{file_list}

Key file contents:
{context}

Create a precise execution plan. Each step must use one of: ListDirectory, Read, Glob, Grep, Write, Bash, Think, WebSearch.
Format:
STEP N: [Tool] description
  args: ...
  expected: ...
"""
    return await model.ask(AGENT_SYSTEM, prompt)


# ---------------------------------------------------------------------------
# Tool metadata for registry
# ---------------------------------------------------------------------------
TOOL_METADATA = [
    {
        "name": "AnalyzeProject",
        "category": "planning",
        "description": "Deep analysis of the project: structure, stack, purpose, architecture.",
        "source_module": "tools.planning",
    },
    {
        "name": "PlanTask",
        "category": "planning",
        "description": "Create a step-by-step execution plan for a task.",
        "source_module": "tools.planning",
    },
]
