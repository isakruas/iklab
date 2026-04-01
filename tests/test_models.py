from __future__ import annotations

import pytest

from iklab.models import AgentConfig, SessionInfo, TurnResult, UsageSummary


def test_agent_config_defaults():
    cfg = AgentConfig()
    assert cfg.model_timeout == 120
    assert "rm -rf /" in cfg.blocked_commands


def test_agent_config_frozen():
    cfg = AgentConfig()
    with pytest.raises(AttributeError):
        cfg.model_name = "other"


def test_turn_result_defaults():
    tr = TurnResult()
    assert tr.content == ""
    assert tr.tool_calls == ()


def test_session_info():
    si = SessionInfo(session_id="abc", messages=({"role": "user", "content": "hi"},))
    assert si.session_id == "abc"
    assert len(si.messages) == 1


def test_usage_summary_total():
    us = UsageSummary(input_tokens=100, output_tokens=50)
    assert us.total_tokens == 150
