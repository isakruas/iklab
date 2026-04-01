from __future__ import annotations

from iklab.models import AgentConfig
from iklab.prompt_builder import build_system_prompt
from iklab.tool_pool import assemble_tool_pool
from iklab.tool_registry import build_tool_registry


def _default_pool():
    return assemble_tool_pool(build_tool_registry())


def test_contains_kernel():
    prompt = build_system_prompt(AgentConfig(), _default_pool())
    assert "KERNEL_PROCESSOR" in prompt


def test_contains_tools():
    prompt = build_system_prompt(AgentConfig(), _default_pool())
    assert "Available Tools" in prompt
    assert "**Read**" in prompt


def test_contains_default_protocol():
    prompt = build_system_prompt(AgentConfig(), _default_pool())
    assert "ORCHESTRATE a specialized protocol" in prompt


def test_expert_protocol_injected():
    prompt = build_system_prompt(
        AgentConfig(),
        _default_pool(),
        expert_protocol="[MODE: REACT_EXPERT]",
    )
    assert "<ACTIVE_EXPERT_PROTOCOL>" in prompt
    assert "[MODE: REACT_EXPERT]" in prompt


def test_history_summary():
    prompt = build_system_prompt(
        AgentConfig(),
        _default_pool(),
        history_summary="User asked to refactor auth module.",
    )
    assert "<HISTORY_SUMMARY>" in prompt
    assert "refactor auth" in prompt


def test_config_hints():
    cfg = AgentConfig(model_name="test-model", max_bash_timeout=30)
    prompt = build_system_prompt(cfg, _default_pool())
    assert "test-model" in prompt
    assert "30s" in prompt


def test_critical_directive():
    prompt = build_system_prompt(AgentConfig(), _default_pool())
    assert "CRITICAL: Use TOOLS, not text." in prompt
