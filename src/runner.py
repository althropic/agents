"""
Entry point for the File Assistant Agent.

Single-shot mode:
    python -m src.runner "summarize src/config.py"
    python -m src.runner --workspace /some/project "summarize src/config.py"

Interactive REPL mode:
    python -m src.runner
    python -m src.runner --workspace /some/project
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import load_config
from src.io import write_output
from src.logger import apply_log_level, get_logger
from src import repl_commands

logger = get_logger(__name__)


def _parse_args() -> tuple[Path, list[str]]:
    """Parse CLI args; return (workspace_path, remaining_prompt_tokens)."""
    parser = argparse.ArgumentParser(
        prog="src.runner",
        description="File Assistant Agent",
        add_help=True,
    )
    parser.add_argument(
        "--workspace",
        metavar="DIR",
        default=None,
        help=(
            "Root directory the agent is allowed to read/write. "
            "Defaults to the current working directory."
        ),
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Optional prompt for single-shot mode. Omit for interactive REPL.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve() if args.workspace else Path.cwd()
    return workspace, args.prompt


def _build_loop(workspace: Path):
    """Load config anchored to *workspace*, apply log level, return AgentLoop."""
    from src.agent.loop import AgentLoop  # noqa: PLC0415

    cfg = load_config(workspace=workspace)
    apply_log_level(cfg.logging.level)
    logger.info(
        "Config loaded: model=%s base_url=%s max_tokens=%d thinking_budget=%d "
        "max_iter=%d max_file_kb=%d memory_persist=%s log_level=%s "
        "allowed_commands=%s timeout=%ds workspace=%s",
        cfg.llm.model,
        cfg.llm.base_url,
        cfg.llm.max_tokens,
        cfg.llm.thinking_budget,
        cfg.agent.max_iterations,
        cfg.agent.max_file_size_kb,
        cfg.memory.persist,
        cfg.logging.level,
        cfg.execution.allowed_commands,
        cfg.execution.timeout_seconds,
        cfg.workspace,
    )
    return AgentLoop(cfg)


def run_once(prompt: str, workspace: Path) -> None:
    """Run a single prompt and print the result."""
    loop = _build_loop(workspace)
    logger.info("Single-shot mode: prompt=%r workspace=%s", prompt[:120], workspace)
    answer = loop.run(prompt)
    write_output(answer)


def run_repl(workspace: Path) -> None:
    """Interactive REPL — memory persists across turns within the session."""
    from src.agent.loop import AgentLoop  # noqa: PLC0415
    from src.agent.memory import Memory   # noqa: PLC0415

    cfg = load_config(workspace=workspace)
    apply_log_level(cfg.logging.level)
    logger.info(
        "Config loaded: model=%s base_url=%s max_tokens=%d thinking_budget=%d "
        "max_iter=%d max_file_kb=%d memory_persist=%s log_level=%s "
        "allowed_commands=%s timeout=%ds workspace=%s",
        cfg.llm.model,
        cfg.llm.base_url,
        cfg.llm.max_tokens,
        cfg.llm.thinking_budget,
        cfg.agent.max_iterations,
        cfg.agent.max_file_size_kb,
        cfg.memory.persist,
        cfg.logging.level,
        cfg.execution.allowed_commands,
        cfg.execution.timeout_seconds,
        cfg.workspace,
    )

    loop = AgentLoop(cfg)
    # Single Memory instance shared across all prompts in the session.
    memory = Memory(
        system_prompt=cfg.agent.system_prompt,
        persist=cfg.memory.persist,
        export_path=str(cfg.resolved_memory_export_path()),
    )

    logger.info("REPL mode started (persistent memory, workspace=%s)", workspace)
    write_output(f"File Assistant Agent — workspace: {workspace}")
    write_output("Type your request, or 'exit' to quit. Type /help for commands.\n")

    while True:
        try:
            prompt = input(">>> ").strip()
        except (KeyboardInterrupt, EOFError):
            write_output("\nBye.")
            logger.info("REPL exited by user")
            memory.maybe_export()
            break

        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit"}:
            write_output("Bye.")
            logger.info("REPL exited by user command")
            memory.maybe_export()
            break

        if repl_commands.is_command(prompt):
            repl_commands.handle(prompt, cfg, memory)
            continue

        try:
            for chunk in loop.stream_with_memory(prompt, memory):
                write_output(chunk)
            write_output("\n")
        except Exception as exc:  # noqa: BLE001
            logger.error("REPL error: %s", exc, exc_info=True)
            write_output(f"\nError: {exc}")


def main() -> None:
    workspace, prompt_tokens = _parse_args()
    if prompt_tokens:
        run_once(" ".join(prompt_tokens), workspace)
    else:
        run_repl(workspace)


if __name__ == "__main__":
    main()
