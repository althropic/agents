"""
OpenAI function-calling schemas for action tools (shell, git, tests).

Kept separate from schemas.py so neither file exceeds the 200-line limit.
Imported by schemas.py and combined into ALL_TOOLS.
"""

from __future__ import annotations

from typing import Any, Dict, List

ACTION_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command. The command name must be in the "
                "allowed commands list. Returns exit code, stdout, and stderr."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": (
                            "Working directory (relative to workspace). "
                            "Defaults to the workspace root."
                        ),
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": (
                "Show the current git status of the workspace "
                "(porcelain format)."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": (
                "Show git diff of the workspace. "
                "Set staged=true to see staged (cached) changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "If true, show staged (cached) changes.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stage all changes and commit with the given message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Commit message.",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run pytest in the workspace and return the results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "string",
                        "description": (
                            "Optional pytest arguments, e.g. '-x --tb=short'."
                        ),
                    },
                },
            },
        },
    },
]
