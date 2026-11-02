"""
OpenAI function-calling schema for the memory_search tool.

Kept separate from schemas.py to avoid exceeding the 200-line limit.
Imported by schemas.py and merged into ALL_TOOLS.
"""

from __future__ import annotations

from typing import Any, Dict, List

MEMORY_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "memory_search",
            "description": (
                "Search the persistent vector memory index for files or "
                "content that are semantically related to a query. "
                "Returns the top matching document paths and snippets. "
                "Use this to find relevant files before reading them, or "
                "to recall context from previous sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural-language description of what you are "
                            "looking for, e.g. 'rate limiting logic' or "
                            "'database connection setup'."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": (
                            "Maximum number of results to return. Defaults to 5."
                        ),
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]
