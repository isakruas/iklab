from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from iklab.tools.execution import _html_to_text, web_fetch

# --- _html_to_text unit tests (no network) ---


def test_strips_tags():
    assert _html_to_text("<p>hello</p>") == "hello"


def test_strips_script_and_style():
    html = "<script>var x=1;</script><style>.a{}</style><p>content</p>"
    assert "content" in _html_to_text(html)
    assert "var x" not in _html_to_text(html)


def test_converts_br_to_newline():
    result = _html_to_text("line1<br>line2")
    assert "line1" in result
    assert "line2" in result


def test_decodes_entities():
    assert "&" in _html_to_text("&amp;")
    assert "<" in _html_to_text("&lt;")


def test_collapses_whitespace():
    result = _html_to_text("<p>  lots   of   spaces  </p>")
    assert "  " not in result


def test_truncates_long_content():
    html = "<p>" + "x" * 50_000 + "</p>"
    result = _html_to_text(html, max_chars=1000)
    assert len(result) < 1100
    assert "Truncated" in result


# --- web_fetch integration tests (mocked HTTP) ---


def _mock_response(text: str, content_type: str = "text/html", status: int = 200):
    resp = AsyncMock()
    resp.text = text
    resp.content = text.encode()
    resp.status_code = status
    resp.headers = {"content-type": content_type}
    resp.raise_for_status = lambda: None
    resp.json = lambda: json.loads(text)
    return resp


@pytest.mark.anyio
async def test_fetch_html():
    html = "<html><body><h1>Title</h1><p>Hello world</p></body></html>"
    mock_resp = _mock_response(html, "text/html")
    with patch("iklab.tools.execution.httpx.AsyncClient") as mock_client:
        ctx = AsyncMock()
        ctx.get = AsyncMock(return_value=mock_resp)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await web_fetch("https://example.com")
        assert "Title" in result
        assert "Hello world" in result
        assert "<h1>" not in result


@pytest.mark.anyio
async def test_fetch_json():
    data = {"key": "value", "num": 42}
    mock_resp = _mock_response(json.dumps(data), "application/json")
    with patch("iklab.tools.execution.httpx.AsyncClient") as mock_client:
        ctx = AsyncMock()
        ctx.get = AsyncMock(return_value=mock_resp)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await web_fetch("https://api.example.com/data")
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["num"] == 42


@pytest.mark.anyio
async def test_fetch_plain_text():
    mock_resp = _mock_response("plain content here", "text/plain")
    with patch("iklab.tools.execution.httpx.AsyncClient") as mock_client:
        ctx = AsyncMock()
        ctx.get = AsyncMock(return_value=mock_resp)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await web_fetch("https://example.com/file.txt")
        assert result == "plain content here"


@pytest.mark.anyio
async def test_fetch_error():
    with patch("iklab.tools.execution.httpx.AsyncClient") as mock_client:
        ctx = AsyncMock()
        ctx.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.return_value.__aenter__ = AsyncMock(return_value=ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await web_fetch("https://unreachable.example.com")
        assert "Fetch error" in result
