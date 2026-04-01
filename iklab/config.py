from __future__ import annotations

import os

from .models import AgentConfig


def load_config() -> AgentConfig:
    """Build an AgentConfig from environment variables with sensible defaults."""
    return AgentConfig(
        model_url=os.environ.get(
            "IKLAB_MODEL_URL",
            AgentConfig.model_url,
        ),
        model_name=os.environ.get(
            "IKLAB_MODEL_NAME",
            AgentConfig.model_name,
        ),
        model_timeout=int(os.environ.get(
            "IKLAB_MODEL_TIMEOUT",
            str(AgentConfig.model_timeout),
        )),
        max_validation_retries=int(os.environ.get(
            "IKLAB_MAX_RETRIES",
            str(AgentConfig.max_validation_retries),
        )),
    )


# Module-level singleton for backward compatibility
_config: AgentConfig | None = None


def get_config() -> AgentConfig:
    """Return the cached config, loading it on first call."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
