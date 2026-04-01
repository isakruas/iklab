from __future__ import annotations

import os
import json
from pathlib import Path

from .models import AgentConfig
from typing import Iterable


def load_config() -> AgentConfig:
    """Build an AgentConfig from environment variables with sensible defaults."""
    # Allow specifying additional tool search paths via env vars or a JSON settings file.
    # Env vars:
    #   IKLAB_TOOL_PATHS (colon-separated)
    #   IKLAB_MCP_SERVERS (colon-separated list of URLs)
    # Settings file (JSON) locations (in order of precedence):
    #   IKLAB_SETTINGS -> path to a JSON file
    #   ./ .iklab/settings.json
    #   ./iklab_tools.json (legacy)
    #   ~/.iklab/settings.json
    raw_tool_paths = os.environ.get("IKLAB_TOOL_PATHS", "")
    raw_mcp_servers = os.environ.get("IKLAB_MCP_SERVERS", "")
    cfg_path_env = os.environ.get("IKLAB_SETTINGS")

    def _parse_paths(s: str) -> tuple[str, ...]:
        if not s:
            return ()
        parts = [p.strip() for p in s.split(":") if p.strip()]
        return tuple(parts)

    # Read JSON settings file if present. Support multiple well-known locations.
    file_tool_paths: tuple[str, ...] = ()
    file_mcp_servers: tuple[str, ...] = ()
    file_skills_paths: tuple[str, ...] = ()

    cfg_file = None
    if cfg_path_env:
        cfg_file = Path(cfg_path_env)
    else:
        # prefer project-local .iklab/settings.json
        cand1 = Path(os.getcwd()) / ".iklab" / "settings.json"
        cand2 = Path(os.getcwd()) / "iklab_tools.json"  # legacy
        cand3 = Path.home() / ".iklab" / "settings.json"
        for c in (cand1, cand2, cand3):
            if c.exists():
                cfg_file = c
                break

    if cfg_file and cfg_file.exists():
        try:
            with cfg_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            tp = data.get("tool_paths")
            if isinstance(tp, list):
                file_tool_paths = tuple(str(x) for x in tp if isinstance(x, str) and x.strip())
            elif isinstance(tp, str):
                file_tool_paths = _parse_paths(tp)

            ms = data.get("mcp_servers") or data.get("mcps")
            if isinstance(ms, list):
                file_mcp_servers = tuple(str(x) for x in ms if isinstance(x, str) and x.strip())
            elif isinstance(ms, str):
                file_mcp_servers = _parse_paths(ms)
            sp = data.get("skills_paths") or data.get("skill_paths")
            file_skills_paths: tuple[str, ...] = ()
            if isinstance(sp, list):
                file_skills_paths = tuple(str(x) for x in sp if isinstance(x, str) and x.strip())
            elif isinstance(sp, str):
                file_skills_paths = _parse_paths(sp)
        except Exception:
            # If config is malformed, ignore and fall back to env/defaults
            file_tool_paths = ()
            file_mcp_servers = ()
            file_skills_paths = ()

    env_paths = _parse_paths(raw_tool_paths)
    raw_skill_paths = os.environ.get("IKLAB_SKILL_PATHS", "")
    env_skill_paths = _parse_paths(raw_skill_paths)
    # parse MCP servers from env
    env_mcp = _parse_paths(raw_mcp_servers)

    # Merge tool paths: file first, then env, then default
    if file_tool_paths:
        seen = set()
        out = []
        for p in list(file_tool_paths) + list(env_paths):
            if p not in seen:
                seen.add(p)
                out.append(p)
        combined = tuple(out)
    elif env_paths:
        combined = env_paths
    else:
        combined = AgentConfig.tools_paths

    # Merge mcp servers: file first, then env
    if file_mcp_servers:
        seen = set()
        out = []
        for p in list(file_mcp_servers) + list(env_mcp):
            if p not in seen:
                seen.add(p)
                out.append(p)
        combined_mcps = tuple(out)
    elif env_mcp:
        combined_mcps = env_mcp
    else:
        combined_mcps = AgentConfig.mcp_servers

    # Merge skills paths: file first, then env, then default
    if file_skills_paths:
        seen = set()
        out = []
        for p in list(file_skills_paths) + list(env_skill_paths):
            if p not in seen:
                seen.add(p)
                out.append(p)
        combined_skills = tuple(out)
    elif env_skill_paths:
        combined_skills = env_skill_paths
    else:
        combined_skills = AgentConfig.skills_paths

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
        tools_paths=combined,
        mcp_servers=combined_mcps,
        skills_paths=combined_skills,
    )


# Module-level singleton for backward compatibility
_config: AgentConfig | None = None


def get_config() -> AgentConfig:
    """Return the cached config, loading it on first call."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
