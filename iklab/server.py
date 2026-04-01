from __future__ import annotations

"""MCP Server — imports all tools and runs the server."""

import os
from . import sandbox

# Set workdir from env (passed by CLI) before importing tools
_wd = os.environ.get("IKLAB_WORKDIR")
if _wd:
    sandbox.set_workdir(_wd)

# Import tool modules to register them on the shared mcp instance
from .tools import mcp  # noqa: E402
from .tools import context, planning, execution  # noqa: E402, F401


def run_server():
    mcp.run()


if __name__ == "__main__":
    run_server()
