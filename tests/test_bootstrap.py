from __future__ import annotations

from iklab.bootstrap import BootstrapGraph, build_bootstrap_graph


def test_build_bootstrap_graph():
    graph = build_bootstrap_graph()
    assert isinstance(graph, BootstrapGraph)
    assert len(graph.stages) == 9


def test_stages_order():
    graph = build_bootstrap_graph()
    assert graph.stages[0] == "load_config"
    assert graph.stages[-1] == "ready"


def test_all_stages_present():
    graph = build_bootstrap_graph()
    expected = {
        "load_config", "set_sandbox", "start_mcp_server",
        "load_tools", "build_registry", "build_tool_pool",
        "build_prompt", "initialize_agent", "ready",
    }
    assert set(graph.stages) == expected


def test_as_markdown():
    graph = build_bootstrap_graph()
    md = graph.as_markdown()
    assert "# Bootstrap Graph" in md
    assert "1. load_config" in md
    assert "9. ready" in md


def test_frozen():
    graph = build_bootstrap_graph()
    try:
        graph.stages = ()  # type: ignore[misc]
        assert False, "Should not allow mutation"
    except AttributeError:
        pass
