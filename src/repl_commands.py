"""
REPL slash-command handler.

Supported commands:
    /think on|off       — enable or disable the reasoning budget
    /model <name>       — switch the active model for this session
    /export [label]     — dump conversation to a markdown file
    /help               — list available commands
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.agent.memory import Memory
from src.config import AppConfig
from src.io import write_output
from src.logger import get_logger

logger = get_logger(__name__)

_COMMANDS = "/think  /model  /export  /help"


def is_command(prompt: str) -> bool:
    """Return True if *prompt* starts with '/'."""
    return prompt.startswith("/")


def handle(prompt: str, cfg: AppConfig, memory: Memory) -> bool:
    """
    Dispatch a slash command.

    Returns True when the command was handled (caller should skip
    sending the prompt to the LLM).  Returns False if the command
    was not recognised (caller may treat as a normal prompt or warn).
    """
    parts = prompt.split(maxsplit=2)
    cmd = parts[0].lower()

    if cmd == "/help":
        write_output(f"Available commands: {_COMMANDS}")
        return True

    if cmd == "/think":
        return _handle_think(parts, cfg)

    if cmd == "/model":
        return _handle_model(parts, cfg)

    if cmd == "/export":
        label = parts[1] if len(parts) > 1 else None
        return _handle_export(memory, cfg, label)

    write_output(f"Unknown command '{cmd}'. Available: {_COMMANDS}")
    return True


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------

def _handle_think(parts: list[str], cfg: AppConfig) -> bool:
    if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
        write_output("Usage: /think on|off")
        return True
    state = parts[1].lower()
    if cfg.llm.thinking_param == "reasoning_effort":
        return _set_thinking_effort(state, cfg)
    return _set_thinking_budget(state, cfg)


def _set_thinking_effort(state: str, cfg: AppConfig) -> bool:
    if state == "off":
        cfg.llm.thinking_effort = "none"
        write_output("Thinking disabled.")
        logger.info("/think off: thinking_effort=none")
        return True
    # on: keep the current level, or restore to "high" when disabled.
    effort = "high" if cfg.llm.thinking_effort == "none" else cfg.llm.thinking_effort
    cfg.llm.thinking_effort = effort
    write_output(f"Thinking enabled (effort={effort}).")
    logger.info("/think on: thinking_effort=%s", effort)
    return True


def _set_thinking_budget(state: str, cfg: AppConfig) -> bool:
    if state == "off":
        cfg.llm.thinking_budget = 0
        write_output("Thinking disabled.")
        logger.info("/think off: thinking_budget=0")
        return True
    # on: keep the current budget, or fall back to 8192 when zeroed.
    budget = cfg.llm.thinking_budget if cfg.llm.thinking_budget > 0 else 8192
    cfg.llm.thinking_budget = budget
    write_output(f"Thinking enabled (budget={budget} tokens).")
    logger.info("/think on: thinking_budget=%d", budget)
    return True


def _handle_model(parts: list[str], cfg: AppConfig) -> bool:
    if len(parts) < 2:
        write_output(f"Current model: {cfg.llm.model}\nUsage: /model <name>")
        return True
    new_model = parts[1]
    old_model = cfg.llm.model
    cfg.llm.model = new_model
    write_output(f"Model switched: {old_model} → {new_model}")
    logger.info("/model: %s → %s", old_model, new_model)
    return True


def _handle_export(
    memory: Memory, cfg: AppConfig, label: Optional[str]
) -> bool:
    export_path = cfg.resolved_memory_export_path()
    # Temporarily point memory's export path at the resolved workspace path.
    memory._export_path = export_path  # noqa: SLF001
    out = memory.export_markdown(label=label)
    write_output(f"Session exported → {out}")
    logger.info("/export: wrote %s", out)
    return True
