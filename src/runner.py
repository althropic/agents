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


def _reasoning_writer(show: bool):
    """Return a callback that renders reasoning trace dimmed, or None when off."""
    if not show:
        return None

    def _write(text: str) -> None:
        write_output(f"\x1b[2m{text}\x1b[0m", end="")

    return _write


def _parse_args() -> tuple[list[Path], list[str]]:
    """Parse CLI args; return (workspace_paths, remaining_prompt_tokens)."""
    parser = argparse.ArgumentParser(
        prog="src.runner",
        description="File Assistant Agent",
        add_help=True,
    )
    parser.add_argument(
        "--workspace",
        metavar="DIR",
        action="append",
        default=None,
        help=(
            "Root directory the agent is allowed to read/write. "
            "Repeat to add multiple workspaces. "
            "Defaults to the current working directory."
        ),
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Optional prompt for single-shot mode. Omit for interactive REPL.",
    )
    args = parser.parse_args()

    workspaces = (
        [Path(w).resolve() for w in args.workspace]
        if args.workspace
        else [Path.cwd()]
    )
    return workspaces, args.prompt


def _build_loop(workspaces: list[Path]):
    """Load config anchored to *workspaces[0]*, apply log level, return AgentLoop."""
    from src.agent.loop import AgentLoop  # noqa: PLC0415

    workspace = workspaces[0]
    cfg = load_config(workspace=workspace)
    # Additional workspaces are merged into allowed_roots so the agent
    # can read/write across all of them.
    for extra in workspaces[1:]:
        cfg.file_access.allowed_roots.append(str(extra))
    apply_log_level(cfg.logging.level)
    logger.info(
        "Config loaded: model=%s base_url=%s max_tokens=%d thinking_effort=%s "
        "thinking_budget=%d max_iter=%d max_file_kb=%d memory_persist=%s log_level=%s "
        "allowed_commands=%s timeout=%ds workspaces=%s",
        cfg.llm.model,
        cfg.llm.base_url,
        cfg.llm.max_tokens,
        cfg.llm.thinking_effort,
        cfg.llm.thinking_budget,
        cfg.agent.max_iterations,
        cfg.agent.max_file_size_kb,
        cfg.memory.persist,
        cfg.logging.level,
        cfg.execution.allowed_commands,
        cfg.execution.timeout_seconds,
        workspaces,
    )
    return AgentLoop(cfg)


def run_once(prompt: str, workspaces: list[Path]) -> None:
    """Run a single prompt and print the result."""
    loop = _build_loop(workspaces)
    logger.info("Single-shot mode: prompt=%r workspaces=%s", prompt[:120], workspaces)
    answer = loop.run(prompt)
    write_output(answer)


def run_repl(workspaces: list[Path]) -> None:
    """Interactive REPL — memory persists across turns within the session."""
    from src.agent.loop import AgentLoop  # noqa: PLC0415
    from src.agent.memory import Memory   # noqa: PLC0415

    workspace = workspaces[0]
    cfg = load_config(workspace=workspace)
    for extra in workspaces[1:]:
        cfg.file_access.allowed_roots.append(str(extra))
    apply_log_level(cfg.logging.level)
    logger.info(
        "Config loaded: model=%s base_url=%s max_tokens=%d thinking_effort=%s "
        "thinking_budget=%d max_iter=%d max_file_kb=%d memory_persist=%s log_level=%s "
        "allowed_commands=%s timeout=%ds workspaces=%s",
        cfg.llm.model,
        cfg.llm.base_url,
        cfg.llm.max_tokens,
        cfg.llm.thinking_effort,
        cfg.llm.thinking_budget,
        cfg.agent.max_iterations,
        cfg.agent.max_file_size_kb,
        cfg.memory.persist,
        cfg.logging.level,
        cfg.execution.allowed_commands,
        cfg.execution.timeout_seconds,
        workspaces,
    )

    loop = AgentLoop(cfg)
    # Single Memory instance shared across all prompts in the session.
    memory = Memory(
        system_prompt=cfg.agent.system_prompt,
        persist=cfg.memory.persist,
        export_path=str(cfg.resolved_memory_export_path()),
    )

    logger.info("REPL mode started (persistent memory, workspaces=%s)", workspaces)
    workspace_display = ", ".join(str(w) for w in workspaces)
    write_output(f"File Assistant Agent — workspace: {workspace_display}")
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
            on_reasoning = _reasoning_writer(cfg.llm.show_reasoning)
            for chunk in loop.stream_with_memory(
                prompt, memory, on_reasoning=on_reasoning
            ):
                write_output(chunk, end="")
            write_output("\n")
        except Exception as exc:  # noqa: BLE001
            logger.error("REPL error: %s", exc, exc_info=True)
            write_output(f"\nError: {exc}")


def main() -> None:
    workspaces, prompt_tokens = _parse_args()
    if prompt_tokens:
        run_once(" ".join(prompt_tokens), workspaces)
    else:
        run_repl(workspaces)


if __name__ == "__main__":
    main()
