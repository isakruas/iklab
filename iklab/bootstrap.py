from __future__ import annotations

"""Bootstrap graph — defines the ordered initialization stages of the agent."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BootstrapGraph:
    """Immutable sequence of bootstrap stages."""

    stages: tuple[str, ...]

    def as_markdown(self) -> str:
        lines = ["# Bootstrap Graph", ""]
        for i, stage in enumerate(self.stages, 1):
            lines.append(f"{i}. {stage}")
        return "\n".join(lines)


def build_bootstrap_graph() -> BootstrapGraph:
    """Return the standard agent bootstrap sequence."""
    return BootstrapGraph(
        stages=(
            "load_config",
            "set_sandbox",
            "start_mcp_server",
            "load_tools",
            "build_registry",
            "build_tool_pool",
            "build_prompt",
            "initialize_agent",
            "ready",
        )
    )
