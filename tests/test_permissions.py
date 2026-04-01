from __future__ import annotations

from iklab.permissions import AUTO_APPROVE_TOOLS, ToolApprover, ToolPermissionContext


def test_empty_context_allows_all():
    ctx = ToolPermissionContext()
    assert ctx.blocks("Read") is False
    assert ctx.blocks("Write") is False


def test_deny_by_name():
    ctx = ToolPermissionContext.from_iterables(deny_names=["Bash"])
    assert ctx.blocks("Bash") is True
    assert ctx.blocks("bash") is True  # case insensitive
    assert ctx.blocks("Read") is False


def test_deny_by_prefix():
    ctx = ToolPermissionContext.from_iterables(deny_prefixes=["mcp_"])
    assert ctx.blocks("mcp_server") is True
    assert ctx.blocks("MCP_Server") is True
    assert ctx.blocks("Read") is False


def test_from_iterables_none():
    ctx = ToolPermissionContext.from_iterables()
    assert ctx.blocks("anything") is False


# --- ToolApprover tests ---


def test_approver_auto_approve_context_tools():
    approver = ToolApprover()
    for tool in AUTO_APPROVE_TOOLS:
        assert approver.approve(tool, "") is True


def test_approver_always_approve_all():
    approver = ToolApprover(always_approve_all=True)
    assert approver.approve("Bash", "command='rm -rf /'") is True
    assert approver.approve("Write", "path='x'") is True


def test_approver_session_approved():
    approver = ToolApprover(always_approve_all=True)
    # After always_approve_all, everything passes without prompt
    assert approver.approve("CustomTool", "") is True


def test_approver_custom_auto_approve():
    approver = ToolApprover(auto_approve=frozenset({"Bash", "Write"}))
    assert approver.approve("Bash", "") is True
    assert approver.approve("Write", "") is True
