from __future__ import annotations

import os

from iklab.config import load_config
from iklab.models import AgentConfig


def test_default_config():
    cfg = load_config()
    assert isinstance(cfg, AgentConfig)
    assert cfg.model_name == "ai/granite-4.0-h-tiny"
    assert cfg.model_timeout == 120


def test_env_override(monkeypatch):
    monkeypatch.setenv("IKLAB_MODEL_NAME", "custom-model")
    monkeypatch.setenv("IKLAB_MODEL_TIMEOUT", "60")
    cfg = load_config()
    assert cfg.model_name == "custom-model"
    assert cfg.model_timeout == 60


def test_config_is_frozen():
    cfg = load_config()
    import pytest
    with pytest.raises(AttributeError):
        cfg.model_name = "other"
