"""
OpenAI function-calling schemas for all agent tools.

File tool schemas are defined here as FILE_TOOLS.
Action tool schemas (shell, git, tests) live in action_schemas.py.
ALL_TOOLS combines both lists for the agent loop.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.agent.action_schemas import ACTION_TOOLS

FILE_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full text content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a file, creating it if it does not exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and subdirectories in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Recursively search for files matching a glob pattern "
                "under a root directory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {
                        "type": "string",
                        "description": "Root directory to search from.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern, e.g. '*.py' or '**/*.md'.",
                    },
                },
                "required": ["root", "pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": (
                "Search for a regex pattern inside a file and return "
                "matching lines with line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to search.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Python regex pattern to search for.",
                    },
                },
                "required": ["path", "pattern"],
            },
        },
    },
]

# Combined list sent to the LLM so it knows every available tool.
ALL_TOOLS: List[Dict[str, Any]] = FILE_TOOLS + ACTION_TOOLS
