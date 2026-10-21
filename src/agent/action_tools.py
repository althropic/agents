"""
Action tools (shell, git, tests) exposed to the LLM via function-calling.

Each tool validates against an allowed-commands list before executing.
Schemas live in action_schemas.py.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------

def _extract_command_name(command: str) -> str:
    """Extract the command name from a command string for allow-list checking."""
    parts = shlex.split(command, posix=(os.name != "nt"))
    if not parts:
        return ""
    name = Path(parts[0].strip("\"'")).name
    if name.lower().endswith(".exe"):
        name = name[:-4]
    return name


def _validate_command(cmd_name: str, allowed_commands: List[str]) -> None:
    """Raise PermissionError if *cmd_name* is not in *allowed_commands*."""
    if cmd_name not in allowed_commands:
        raise PermissionError(
            f"Command '{cmd_name}' is not in the allowed commands: "
            f"{allowed_commands}"
        )


def _resolve_cwd(cwd: Optional[str], workspace: Path) -> Path:
    """Resolve *cwd* relative to *workspace* and verify it is inside it."""
    if not cwd:
        return workspace
    p = Path(cwd)
    target = p.resolve() if p.is_absolute() else (workspace / cwd).resolve()
    if not target.is_relative_to(workspace):
        raise PermissionError(
            f"Working directory '{target}' is outside workspace."
        )
    return target


def _format_result(result: subprocess.CompletedProcess) -> str:
    """Format a CompletedProcess into a readable string."""
    parts = [f"Exit code: {result.returncode}"]
    if result.stdout:
        parts.append(f"--- stdout ---\n{result.stdout.rstrip()}")
    if result.stderr:
        parts.append(f"--- stderr ---\n{result.stderr.rstrip()}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def run_command(
    command: str,
    cwd: Optional[str],
    allowed_commands: List[str],
    workspace: Path,
    timeout: int = 30,
) -> str:
    """Run *command* (shell) in *cwd* and return formatted output."""
    cmd_name = _extract_command_name(command)
    _validate_command(cmd_name, allowed_commands)
    cwd_path = _resolve_cwd(cwd, workspace)

    logger.info("run_command: %s in %s", command, cwd_path)
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("run_command timed out after %ds: %s", timeout, command)
        return f"Timeout: command exceeded {timeout}s"
    return _format_result(result)


def git_status(
    workspace: Path,
    allowed_commands: List[str],
    timeout: int = 30,
) -> str:
    """Run `git status --porcelain` in the workspace."""
    _validate_command("git", allowed_commands)
    logger.info("git_status in %s", workspace)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Timeout: git status exceeded {timeout}s"
    return _format_result(result)


def git_diff(
    staged: bool,
    workspace: Path,
    allowed_commands: List[str],
    timeout: int = 30,
) -> str:
    """Run `git diff` (or `git diff --cached`) in the workspace."""
    _validate_command("git", allowed_commands)
    cmd = ["git", "diff", "--cached"] if staged else ["git", "diff"]
    logger.info("git_diff %s in %s", "staged" if staged else "unstaged", workspace)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Timeout: git diff exceeded {timeout}s"
    return _format_result(result)


def git_commit(
    message: str,
    workspace: Path,
    allowed_commands: List[str],
    timeout: int = 30,
) -> str:
    """Stage all changes and commit with *message*."""
    _validate_command("git", allowed_commands)
    logger.info("git_commit in %s", workspace)
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Timeout: git commit exceeded {timeout}s"
    return _format_result(result)


def run_tests(
    args: Optional[str],
    workspace: Path,
    allowed_commands: List[str],
    timeout: int = 60,
) -> str:
    """Run pytest in the workspace and return formatted output."""
    _validate_command("pytest", allowed_commands)
    cmd = [sys.executable, "-m", "pytest"]
    if args:
        cmd += shlex.split(args)
    logger.info("run_tests in %s args=%s", workspace, args)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Timeout: pytest exceeded {timeout}s"
    return _format_result(result)


def build_action_tool_map(
    allowed_commands: List[str],
    workspace: Path,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Return name -> callable mapping with params pre-bound."""
    return {
        "run_command": lambda command, cwd=None: run_command(
            command, cwd, allowed_commands, workspace, timeout
        ),
        "git_status": lambda **kw: git_status(
            workspace, allowed_commands, timeout
        ),
        "git_diff": lambda staged=False, **kw: git_diff(
            staged, workspace, allowed_commands, timeout
        ),
        "git_commit": lambda message, **kw: git_commit(
            message, workspace, allowed_commands, timeout
        ),
        "run_tests": lambda args=None, **kw: run_tests(
            args, workspace, allowed_commands, timeout
        ),
    }
