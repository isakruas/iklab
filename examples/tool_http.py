"""Example custom tool: HTTP requests.

Adds GET/POST tools for interacting with APIs.
"""

from __future__ import annotations

import json

import httpx

from iklab.tools import mcp


@mcp.tool(name="HttpGet")
async def http_get(url: str, headers: str = "") -> str:
    """Make an HTTP GET request. Headers as JSON string: '{"Auth": "Bearer ..."}'"""
    h = json.loads(headers) if headers else {}
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers=h)
            body = resp.text[:5000]
            return f"[{resp.status_code}]\n{body}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="HttpPost")
async def http_post(url: str, body: str = "{}", headers: str = "") -> str:
    """Make an HTTP POST request. Body and headers as JSON strings."""
    h = json.loads(headers) if headers else {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.post(url, content=body, headers=h)
            result = resp.text[:5000]
            return f"[{resp.status_code}]\n{result}"
    except Exception as e:
        return f"Error: {e}"


TOOL_METADATA = [
    {
        "name": "HttpGet",
        "category": "execution",
        "description": "Make an HTTP GET request to a URL.",
        "source_module": "tools.http",
    },
    {
        "name": "HttpPost",
        "category": "execution",
        "description": "Make an HTTP POST request to a URL.",
        "source_module": "tools.http",
    },
]
