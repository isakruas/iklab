"""Central tool registry — discovers and indexes all MCP tool metadata."""

from __future__ import annotations

import importlib
import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

from .config import get_config


@dataclass(frozen=True)
class ToolMeta:
    """Immutable metadata for a single registered tool."""

    name: str
    category: str  # "context", "planning", "execution"
    description: str
    source_module: str  # "tools.context", "tools.planning", etc.


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
        matches = [t for t in self.tools if q in t.name.lower() or q in t.description.lower()]
        return matches[:limit]

    def by_category(self, category: str) -> tuple[ToolMeta, ...]:
        """Return all tools in the given category."""
        return tuple(t for t in self.tools if t.category == category)

    def names(self) -> list[str]:
        """Return a sorted list of all tool names."""
        return sorted(t.name for t in self.tools)


def build_tool_registry() -> ToolRegistry:
    """Build the registry by collecting TOOL_METADATA from all tool modules.

    This will import the built-in `iklab.tools` modules and any additional
    modules found under paths listed in the configuration (env var
    IKLAB_TOOL_PATHS or AgentConfig.tools_paths).
    """
    # Start with the packaged tools (keep existing behaviour)
    builtins: list[str] = (
        "iklab.tools.context",
        "iklab.tools.planning",
        "iklab.tools.execution",
    )

    all_meta: list[ToolMeta] = []

    # Helper to import a module object from a filesystem path file
    def _import_from_path(py_path: Path, mod_name: str):
        spec = importlib.util.spec_from_file_location(mod_name, str(py_path))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[arg-type]
            return mod
        return None

    # Import builtin modules first
    for mod_name in builtins:
        try:
            module = importlib.import_module(mod_name)
        except Exception:
            # If a builtin is missing, skip it — tests rely on being resilient
            continue
        for entry in getattr(module, "TOOL_METADATA", []):
            all_meta.append(
                ToolMeta(
                    name=entry["name"],
                    category=entry["category"],
                    description=entry["description"],
                    source_module=entry["source_module"],
                )
            )

    # Now import any additional tool modules from configured paths
    cfg = get_config()
    for path in getattr(cfg, "tools_paths", ()):  # type: ignore[attr-defined]
        if not path:
            continue

        # Normalize package-like paths: allow both 'iklab.tools' and 'iklab/tools'
        pkg_path = path.replace("/", ".")
        try:
            module = importlib.import_module(pkg_path)
            for entry in getattr(module, "TOOL_METADATA", []):
                all_meta.append(
                    ToolMeta(
                        name=entry["name"],
                        category=entry["category"],
                        description=entry["description"],
                        source_module=entry["source_module"],
                    )
                )
            continue
        except Exception:
            # Not importable as package — try filesystem path
            pass

        # Filesystem path
        fs = Path(path)
        if not fs.exists():
            # try relative to current working dir
            fs = Path(os.getcwd()) / path
        if fs.exists() and fs.is_dir():
            for py in sorted(fs.glob("*.py")):
                if py.name == "__init__.py":
                    # If the directory is a package, import it by path
                    try:
                        pkg_mod = importlib.import_module(path.replace("/", "."))
                        for entry in getattr(pkg_mod, "TOOL_METADATA", []):
                            all_meta.append(
                                ToolMeta(
                                    name=entry["name"],
                                    category=entry["category"],
                                    description=entry["description"],
                                    source_module=entry["source_module"],
                                )
                            )
                        break
                    except Exception:
                        # Fall back to importing files individually
                        pass
                if py.is_file():
                    mod = _import_from_path(py, f"iklab.discovered_tools.{py.stem}")
                    if not mod:
                        continue
                    for entry in getattr(mod, "TOOL_METADATA", []):
                        all_meta.append(
                            ToolMeta(
                                name=entry["name"],
                                category=entry["category"],
                                description=entry["description"],
                                source_module=entry.get("source_module", str(py)),
                            )
                        )

    return ToolRegistry(tools=tuple(all_meta))
