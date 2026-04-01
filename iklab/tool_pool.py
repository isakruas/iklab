"""Tool pool — filters available tools by mode, phase, and permissions."""

from __future__ import annotations

from dataclasses import dataclass

from .permissions import ToolPermissionContext
from .tool_registry import ToolMeta, ToolRegistry

# Tools allowed when simple_mode is active
SIMPLE_TOOLS = frozenset({"Read", "ListDirectory", "Glob", "Grep"})


@dataclass(frozen=True)
class ToolPool:
    """Filtered set of tools available for the current context."""

    tools: tuple[ToolMeta, ...]
    simple_mode: bool
    permission_context: ToolPermissionContext | None

    def as_markdown(self) -> str:
        """Render the pool as a markdown list grouped by category."""
        if not self.tools:
            return "No tools available."
        by_cat: dict[str, list[ToolMeta]] = {}
        for t in self.tools:
            by_cat.setdefault(t.category, []).append(t)
        lines: list[str] = ["# Available Tools", ""]
        for cat in sorted(by_cat):
            lines.append(f"## {cat.title()}")
            for t in by_cat[cat]:
                lines.append(f"- **{t.name}**: {t.description}")
            lines.append("")
        if self.simple_mode:
            lines.append("_Running in simple mode — limited tool set._")
        return "\n".join(lines)

    def names(self) -> list[str]:
        """Return sorted tool names in this pool."""
        return sorted(t.name for t in self.tools)


def assemble_tool_pool(
    registry: ToolRegistry,
    simple_mode: bool = False,
    permission_context: ToolPermissionContext | None = None,
    phase: str = "execution",
) -> ToolPool:
    """Build a ToolPool by applying mode, phase, and permission filters.

    Parameters
    ----------
    registry:
        The full tool registry.
    simple_mode:
        When True, only context tools (Read, ListDirectory, Glob, Grep) are kept.
    permission_context:
        Optional deny-list based filter.
    phase:
        One of "plan", "verify", "execution".
        - "plan"/"verify" restrict to the plan_tools / verify_tools sets
          defined in AgentConfig.
        - "execution" allows all tools.
    """
    from .config import get_config

    cfg = get_config()
    candidates = list(registry.tools)

    # Phase filter
    if phase == "plan":
        allowed = cfg.plan_tools
        candidates = [t for t in candidates if t.name in allowed]
    elif phase == "verify":
        allowed = cfg.verify_tools
        candidates = [t for t in candidates if t.name in allowed]

    # Simple mode filter
    if simple_mode:
        candidates = [t for t in candidates if t.name in SIMPLE_TOOLS]

    # Permission deny-list filter
    if permission_context is not None:
        candidates = [t for t in candidates if not permission_context.blocks(t.name)]

    return ToolPool(
        tools=tuple(candidates),
        simple_mode=simple_mode,
        permission_context=permission_context,
    )
