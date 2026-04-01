"""MCP tool definitions — each file registers tools on the shared `mcp` instance."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("iklab")
