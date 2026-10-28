"""
Web tools exposed to the LLM via OpenAI function-calling.

Provides web_fetch() — fetches a public URL and returns plain text.
Schemas live in web_schemas.py.
"""

from __future__ import annotations

import re
from typing import Any, Dict

import httpx

from src.logger import get_logger

logger = get_logger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\n{3,}")


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse excess blank lines."""
    text = _TAG_RE.sub(" ", html)
    # Collapse runs of spaces inside lines
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Collapse more than two consecutive newlines
    text = _WHITESPACE_RE.sub("\n\n", text)
    return text.strip()


def web_fetch(
    url: str,
    max_kb: int = 100,
    timeout: int = 15,
) -> str:
    """Fetch *url* and return its plain-text content.

    Raises ValueError if the URL scheme is not http/https, if the
    response is not a text content type, or if the response exceeds
    *max_kb* kilobytes.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Only http/https URLs are supported, got: {url!r}")

    logger.info("web_fetch: GET %s", url)
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "file-assistant-agent/1.0"},
        )
    except httpx.TimeoutException:
        logger.warning("web_fetch: timeout after %ds for %s", timeout, url)
        return f"Timeout: request to {url!r} exceeded {timeout}s"
    except httpx.RequestError as exc:
        logger.error("web_fetch: request error for %s: %s", url, exc)
        return f"Error fetching {url!r}: {exc}"

    content_type = response.headers.get("content-type", "")
    if not any(t in content_type for t in ("text/", "application/json", "application/xml")):
        raise ValueError(
            f"Unsupported content type {content_type!r} for {url!r}. "
            "Only text/*, application/json, and application/xml are supported."
        )

    size_kb = len(response.content) / 1024
    if size_kb > max_kb:
        raise ValueError(
            f"Response from {url!r} is {size_kb:.1f} KB, "
            f"exceeds limit of {max_kb} KB."
        )

    if "text/html" in content_type:
        text = _strip_html(response.text)
    else:
        text = response.text.strip()

    logger.info(
        "web_fetch: fetched %s — %d chars (%.1f KB) status=%d",
        url, len(text), size_kb, response.status_code,
    )
    return text


def build_web_tool_map(
    max_kb: int = 100,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Return name → callable mapping with max_kb and timeout pre-bound."""
    return {
        "web_fetch": lambda url, **kw: web_fetch(url, max_kb, timeout),
    }
