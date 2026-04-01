from __future__ import annotations

"""Central tool registry — discovers and indexes all MCP tool metadata."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolMeta:
    """Immutable metadata for a single registered tool."""

    name: str
    category: str          # "context", "planning", "execution"
    description: str
    source_module: str      # "tools.context", "tools.planning", etc.


@dataclass(frozen=True)
class ToolRegistry:
    """Immutable registry of all known tools with search and filtering."""

    tools: tuple[ToolMeta, ...]

    def get(self, name: str) -> ToolMeta | None:
        """Return the ToolMeta for *name*, or None."""
        for t in self.tools:
            if t.name == name:
                return t
        return None

    def find(self, query: str, limit: int = 20) -> list[ToolMeta]:
        """Search tools by name or description substring (case-insensitive)."""
        q = query.lower()
        matches = [
            t for t in self.tools
            if q in t.name.lower() or q in t.description.lower()
        ]
        return matches[:limit]

    def by_category(self, category: str) -> tuple[ToolMeta, ...]:
        """Return all tools in the given category."""
        return tuple(t for t in self.tools if t.category == category)

    def names(self) -> list[str]:
        """Return a sorted list of all tool names."""
        return sorted(t.name for t in self.tools)


def build_tool_registry() -> ToolRegistry:
    """Build the registry by collecting TOOL_METADATA from all tool modules."""
    from .tools import context, planning, execution

    all_meta: list[ToolMeta] = []
    for module in (context, planning, execution):
        for entry in getattr(module, "TOOL_METADATA", []):
            all_meta.append(ToolMeta(
                name=entry["name"],
                category=entry["category"],
                description=entry["description"],
                source_module=entry["source_module"],
            ))
    return ToolRegistry(tools=tuple(all_meta))
