from __future__ import annotations

from iklab.permissions import ToolPermissionContext
from iklab.tool_pool import SIMPLE_TOOLS, ToolPool, assemble_tool_pool
from iklab.tool_registry import ToolMeta, ToolRegistry, build_tool_registry


def _full_registry() -> ToolRegistry:
    return build_tool_registry()


def test_assemble_default():
    pool = assemble_tool_pool(_full_registry())
    assert len(pool.tools) > 0
    assert not pool.simple_mode
    assert pool.permission_context is None


def test_simple_mode():
    pool = assemble_tool_pool(_full_registry(), simple_mode=True)
    assert pool.simple_mode
    for t in pool.tools:
        assert t.name in SIMPLE_TOOLS


def test_phase_plan():
    pool = assemble_tool_pool(_full_registry(), phase="plan")
    names = pool.names()
    # plan_tools default = {ListDirectory, Read, Glob, Grep}
    for n in names:
        assert n in {"ListDirectory", "Read", "Glob", "Grep"}


def test_phase_verify():
    pool = assemble_tool_pool(_full_registry(), phase="verify")
    names = pool.names()
    for n in names:
        assert n in {"ListDirectory", "Read", "Glob", "Grep"}


def test_permission_deny():
    ctx = ToolPermissionContext.from_iterables(deny_names=["Bash"])
    pool = assemble_tool_pool(_full_registry(), permission_context=ctx)
    assert "Bash" not in pool.names()


def test_permission_deny_prefix():
    ctx = ToolPermissionContext.from_iterables(deny_prefixes=["web"])
    pool = assemble_tool_pool(_full_registry(), permission_context=ctx)
    assert "WebSearch" not in pool.names()


def test_as_markdown():
    pool = assemble_tool_pool(_full_registry())
    md = pool.as_markdown()
    assert "# Available Tools" in md
    assert "**Read**" in md


def test_as_markdown_simple():
    pool = assemble_tool_pool(_full_registry(), simple_mode=True)
    md = pool.as_markdown()
    assert "simple mode" in md


def test_names_sorted():
    pool = assemble_tool_pool(_full_registry())
    names = pool.names()
    assert names == sorted(names)


def test_combined_filters():
    ctx = ToolPermissionContext.from_iterables(deny_names=["Read"])
    pool = assemble_tool_pool(_full_registry(), simple_mode=True, permission_context=ctx)
    names = pool.names()
    assert "Read" not in names
    for n in names:
        assert n in SIMPLE_TOOLS
