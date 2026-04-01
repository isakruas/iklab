from __future__ import annotations

from iklab.tool_registry import ToolMeta, ToolRegistry, build_tool_registry


def _sample_registry() -> ToolRegistry:
    return ToolRegistry(tools=(
        ToolMeta(name="Read", category="context", description="Read a file", source_module="tools.context"),
        ToolMeta(name="Write", category="execution", description="Write a file", source_module="tools.execution"),
        ToolMeta(name="Bash", category="execution", description="Run a shell command", source_module="tools.execution"),
        ToolMeta(name="PlanTask", category="planning", description="Create a plan", source_module="tools.planning"),
    ))


def test_get_found():
    reg = _sample_registry()
    meta = reg.get("Read")
    assert meta is not None
    assert meta.name == "Read"
    assert meta.category == "context"


def test_get_not_found():
    reg = _sample_registry()
    assert reg.get("NonExistent") is None


def test_find_by_name():
    reg = _sample_registry()
    results = reg.find("bash")
    assert len(results) == 1
    assert results[0].name == "Bash"


def test_find_by_description():
    reg = _sample_registry()
    results = reg.find("file")
    assert len(results) == 2  # Read + Write
    names = {r.name for r in results}
    assert names == {"Read", "Write"}


def test_find_with_limit():
    reg = _sample_registry()
    results = reg.find("a", limit=2)
    assert len(results) <= 2


def test_by_category():
    reg = _sample_registry()
    execution = reg.by_category("execution")
    assert len(execution) == 2
    assert all(t.category == "execution" for t in execution)


def test_by_category_empty():
    reg = _sample_registry()
    assert reg.by_category("unknown") == ()


def test_names():
    reg = _sample_registry()
    assert reg.names() == ["Bash", "PlanTask", "Read", "Write"]


def test_build_tool_registry():
    reg = build_tool_registry()
    assert len(reg.tools) > 0
    # All standard tools should be present
    names = reg.names()
    assert "Read" in names
    assert "Write" in names
    assert "Bash" in names
    assert "Glob" in names
    assert "Grep" in names
    assert "AnalyzeProject" in names
    assert "PlanTask" in names


def test_frozen():
    meta = ToolMeta(name="X", category="c", description="d", source_module="m")
    try:
        meta.name = "Y"  # type: ignore[misc]
        assert False, "Should not allow mutation"
    except AttributeError:
        pass
