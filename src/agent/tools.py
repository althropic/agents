"""
File tools exposed to the LLM via OpenAI function-calling.

Each tool is a plain Python function.  Schemas live in schemas.py.
ALL_TOOLS is re-exported here for convenience; import it from either module.
TOOL_MAP maps function names to callables for the agent loop.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agent.schemas import ALL_TOOLS  # noqa: F401 — re-exported for callers
from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------

def _resolve_and_check(
    path: str,
    allowed_roots: List[Path],
    max_size_kb: int = 100,
    check_size: bool = False,
    workspace: Optional[Path] = None,
) -> Path:
    """Resolve *path* and verify it sits under one of *allowed_roots*.

    Relative paths are resolved against *workspace* when provided,
    falling back to the first allowed root, then os.getcwd().  This
    ensures ``agent --workspace /other/project`` sees relative paths
    relative to that project, not the shell's cwd.
    """
    p = Path(path)
    if p.is_absolute():
        target = p.resolve()
    else:
        anchor = workspace or (allowed_roots[0] if allowed_roots else None)
        target = (anchor / p).resolve() if anchor else p.resolve()
    if not any(target == root or target.is_relative_to(root) for root in allowed_roots):
        raise PermissionError(
            f"Access denied: '{target}' is outside allowed roots."
        )
    if check_size and target.is_file():
        size_kb = target.stat().st_size / 1024
        if size_kb > max_size_kb:
            raise ValueError(
                f"File '{target}' is {size_kb:.1f} KB, "
                f"exceeds limit of {max_size_kb} KB."
            )
    return target


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def read_file(
    path: str,
    allowed_roots: List[Path],
    max_size_kb: int = 100,
    workspace: Optional[Path] = None,
) -> str:
    """Return the text contents of a file."""
    logger.debug("read_file: path=%s", path)
    target = _resolve_and_check(path, allowed_roots, max_size_kb, check_size=True, workspace=workspace)
    content = target.read_text(encoding="utf-8")
    logger.debug("read_file: read %d chars from %s", len(content), target)
    return content


def write_file(
    path: str,
    content: str,
    allowed_roots: List[Path],
    workspace: Optional[Path] = None,
) -> str:
    """Write *content* to *path*, creating parent dirs as needed."""
    logger.debug("write_file: path=%s len=%d", path, len(content))
    target = _resolve_and_check(path, allowed_roots, workspace=workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    logger.info("write_file: wrote %d chars to %s", len(content), target)
    return f"Written {len(content)} characters to {target}"


def list_dir(
    path: str,
    allowed_roots: List[Path],
    workspace: Optional[Path] = None,
) -> str:
    """List files and subdirectories at *path*, one entry per line."""
    logger.debug("list_dir: path=%s", path)
    target = _resolve_and_check(path, allowed_roots, workspace=workspace)
    if not target.is_dir():
        raise NotADirectoryError(f"'{target}' is not a directory.")
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
    lines = [
        f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in entries
    ]
    result = "\n".join(lines) if lines else "(empty directory)"
    logger.debug("list_dir: %d entries in %s", len(lines), target)
    return result


def search_files(
    root: str,
    pattern: str,
    allowed_roots: List[Path],
) -> str:
    """Recursively find files whose names match glob *pattern* under *root*."""
    logger.debug("search_files: root=%s pattern=%s", root, pattern)
    target = _resolve_and_check(root, allowed_roots)
    if not target.is_dir():
        raise NotADirectoryError(f"'{target}' is not a directory.")
    matches = sorted(target.rglob(pattern))
    lines = [str(m.relative_to(target)) for m in matches]
    result = "\n".join(lines) if lines else "(no matches)"
    logger.debug("search_files: %d matches for '%s' in %s", len(lines), pattern, target)
    return result


def grep(
    path: str,
    pattern: str,
    allowed_roots: List[Path],
    max_size_kb: int = 100,
) -> str:
    """Search for regex *pattern* in *path* and return matching lines with numbers."""
    logger.debug("grep: path=%s pattern=%s", path, pattern)
    target = _resolve_and_check(path, allowed_roots, max_size_kb, check_size=True)
    regex = re.compile(pattern)
    lines = target.read_text(encoding="utf-8").splitlines()
    hits = [
        f"{i + 1}: {line}"
        for i, line in enumerate(lines)
        if regex.search(line)
    ]
    result = "\n".join(hits) if hits else "(no matches)"
    logger.debug("grep: %d hits for '%s' in %s", len(hits), pattern, target)
    return result


def build_tool_map(
    allowed_roots: List[Path],
    max_size_kb: int = 100,
    allowed_commands: List[str] | None = None,
    workspace: Path | None = None,
    command_timeout: int = 30,
    web_fetch_enabled: bool = False,
    web_fetch_max_kb: int = 100,
    web_fetch_timeout: int = 15,
) -> Dict[str, Any]:
    """
    Return a name → callable mapping with allowed_roots and max_size_kb
    already bound, ready for the agent loop to call directly.
    """
    from src.agent.action_tools import build_action_tool_map  # noqa: PLC0415
    from src.agent.web_tools import build_web_tool_map  # noqa: PLC0415

    tool_map: Dict[str, Any] = {
        "read_file": lambda path: read_file(path, allowed_roots, max_size_kb),
        "write_file": lambda path, content: write_file(path, content, allowed_roots),
        "list_dir": lambda path: list_dir(path, allowed_roots),
        "search_files": lambda root, pattern: search_files(root, pattern, allowed_roots),
        "grep": lambda path, pattern: grep(path, pattern, allowed_roots, max_size_kb),
    }
    if allowed_commands and workspace:
        tool_map.update(
            build_action_tool_map(allowed_commands, workspace, command_timeout)
        )
    if web_fetch_enabled:
        tool_map.update(build_web_tool_map(web_fetch_max_kb, web_fetch_timeout))
    return tool_map
