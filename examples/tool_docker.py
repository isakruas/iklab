"""Example custom tool: Docker operations.

Inspect containers, images, and logs.
"""

from __future__ import annotations

import subprocess

from iklab.tools import mcp
from iklab import sandbox


@mcp.tool(name="DockerPs")
def docker_ps(all_containers: bool = False) -> str:
    """List running Docker containers (or all with all_containers=True)."""
    cmd = ["docker", "ps", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}"]
    if all_containers:
        cmd.append("-a")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() or "(no containers)"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="DockerLogs")
def docker_logs(container: str, tail: int = 50) -> str:
    """Show recent logs from a Docker container."""
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(tail), container],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout + result.stderr
        return output.strip()[:5000] or "(no logs)"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="DockerImages")
def docker_images() -> str:
    """List local Docker images."""
    try:
        result = subprocess.run(
            ["docker", "images", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() or "(no images)"
    except Exception as e:
        return f"Error: {e}"


TOOL_METADATA = [
    {
        "name": "DockerPs",
        "category": "context",
        "description": "List running Docker containers.",
        "source_module": "tools.docker",
    },
    {
        "name": "DockerLogs",
        "category": "context",
        "description": "Show recent logs from a Docker container.",
        "source_module": "tools.docker",
    },
    {
        "name": "DockerImages",
        "category": "context",
        "description": "List local Docker images.",
        "source_module": "tools.docker",
    },
]
