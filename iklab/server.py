from __future__ import annotations

"""MCP Server — imports all tools and runs the server."""

import importlib
import importlib.util
import os
from pathlib import Path

from . import sandbox
from .config import get_config

# Set workdir from env (passed by CLI) before importing tools
_wd = os.environ.get("IKLAB_WORKDIR")
if _wd:
    sandbox.set_workdir(_wd)

# Import tool modules to register them on the shared mcp instance
from .tools import mcp  # noqa: E402


def _import_module_from_path(py_path: Path, mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, str(py_path))
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[arg-type]
        return mod
    return None


# Import the packaged tool modules first (keep original behaviour)
try:
    importlib.import_module("iklab.tools.context")
    importlib.import_module("iklab.tools.planning")
    importlib.import_module("iklab.tools.execution")
except Exception:
    # tolerate import failures; tests may not require all of them
    pass

# Also import any configured external tool modules for their side-effects
cfg = get_config()
for path in getattr(cfg, "tools_paths", ()):  # type: ignore[attr-defined]
    if not path:
        continue
    pkg_like = path.replace("/", ".")
    try:
        importlib.import_module(pkg_like)
        continue
    except Exception:
        # Try filesystem
        pass
    fs = Path(path)
    if not fs.exists():
        fs = Path(os.getcwd()) / path
    if fs.exists() and fs.is_dir():
        # If it's a package, import by name if possible
        if (fs / "__init__.py").exists():
            try:
                importlib.import_module(pkg_like)
                continue
            except Exception:
                pass
        for py in sorted(fs.glob("*.py")):
            if py.name == "__init__.py":
                continue
            try:
                _import_module_from_path(py, f"iklab.external_tools.{py.stem}")
            except Exception:
                continue


def run_server():
    mcp.run()


if __name__ == "__main__":
    run_server()
