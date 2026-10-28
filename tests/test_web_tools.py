"""
Unit tests for src/agent/web_tools.py — web_fetch tool.

All HTTP calls are mocked via unittest.mock.patch — no real network needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.web_tools import build_web_tool_map, web_fetch
from src.agent.tools import build_tool_map
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(
    text: str,
    content_type: str = "text/plain",
    status_code: int = 200,
    size_override: int | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.status_code = status_code
    resp.headers = {"content-type": content_type}
    resp.content = (text * (size_override or 1)).encode()
    return resp


# ---------------------------------------------------------------------------
# web_fetch — happy paths
# ---------------------------------------------------------------------------

class TestWebFetchHappyPath:
    def test_plain_text_response(self):
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_response("hello world")
            result = web_fetch("https://example.com/file.txt")
        assert "hello world" in result

    def test_json_response(self):
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(
                '{"key": "value"}', content_type="application/json"
            )
            result = web_fetch("https://api.example.com/data")
        assert '"key"' in result

    def test_html_tags_stripped(self):
        html = "<html><body><h1>Title</h1><p>Content here.</p></body></html>"
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(html, content_type="text/html")
            result = web_fetch("https://example.com/page.html")
        assert "<html>" not in result
        assert "Title" in result
        assert "Content here" in result

    def test_passes_timeout_to_httpx(self):
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_response("ok")
            web_fetch("https://example.com", timeout=5)
        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs["timeout"] == 5


# ---------------------------------------------------------------------------
# web_fetch — guards
# ---------------------------------------------------------------------------

class TestWebFetchGuards:
    def test_rejects_non_http_url(self):
        with pytest.raises(ValueError, match="http"):
            web_fetch("ftp://example.com/file")

    def test_rejects_unsupported_content_type(self):
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(
                "binary", content_type="application/octet-stream"
            )
            with pytest.raises(ValueError, match="Unsupported content type"):
                web_fetch("https://example.com/file.bin")

    def test_rejects_oversized_response(self):
        big_text = "x" * 1024  # 1 KB of text
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(big_text, size_override=200)
            with pytest.raises(ValueError, match="exceeds limit"):
                web_fetch("https://example.com/big.txt", max_kb=1)

    def test_timeout_returns_message(self):
        import httpx as _httpx
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.side_effect = _httpx.TimeoutException("timed out")
            result = web_fetch("https://example.com", timeout=1)
        assert "Timeout" in result

    def test_request_error_returns_message(self):
        import httpx as _httpx
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.side_effect = _httpx.RequestError("connection refused")
            result = web_fetch("https://example.com")
        assert "Error" in result


# ---------------------------------------------------------------------------
# build_web_tool_map
# ---------------------------------------------------------------------------

class TestBuildWebToolMap:
    def test_has_web_fetch_key(self):
        tool_map = build_web_tool_map()
        assert "web_fetch" in tool_map

    def test_calls_web_fetch_via_map(self):
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_response("via map")
            tool_map = build_web_tool_map()
            result = tool_map["web_fetch"](url="https://example.com")
        assert "via map" in result


# ---------------------------------------------------------------------------
# build_tool_map integration
# ---------------------------------------------------------------------------

class TestBuildToolMapWebIntegration:
    def test_web_fetch_absent_when_disabled(self, tmp_workspace: Path):
        tool_map = build_tool_map([tmp_workspace.resolve()])
        assert "web_fetch" not in tool_map

    def test_web_fetch_present_when_enabled(self, tmp_workspace: Path):
        tool_map = build_tool_map(
            [tmp_workspace.resolve()],
            web_fetch_enabled=True,
        )
        assert "web_fetch" in tool_map

    def test_web_fetch_via_combined_map(self, tmp_workspace: Path):
        with patch("src.agent.web_tools.httpx.get") as mock_get:
            mock_get.return_value = _mock_response("combined map")
            tool_map = build_tool_map(
                [tmp_workspace.resolve()],
                web_fetch_enabled=True,
            )
            result = tool_map["web_fetch"](url="https://example.com")
        assert "combined map" in result
