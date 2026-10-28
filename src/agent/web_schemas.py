"""
OpenAI function-calling schemas for web tools.

Kept separate from schemas.py so neither file exceeds the 200-line limit.
Imported by schemas.py and combined into ALL_TOOLS.
"""

from __future__ import annotations

from typing import Any, Dict, List

WEB_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "Fetch the text content of a public URL. "
                "Use this to retrieve documentation, API specs, "
                "changelogs, or any public web page. "
                "Returns plain text with HTML tags stripped."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to fetch (must be http or https).",
                    },
                },
                "required": ["url"],
            },
        },
    },
]
