"""
Entry point for the File Assistant Agent.

Single-shot mode:
    python -m src.runner "summarize src/config.py"

Interactive REPL mode:
    python -m src.runner
"""

from __future__ import annotations

import sys

from src.config import load_config
from src.logger import apply_log_level, get_logger

logger = get_logger(__name__)


def _build_loop():
    """Load config, apply log level, and return a ready AgentLoop."""
    # Import here so logger is initialised before any agent import
    from src.agent.loop import AgentLoop  # noqa: PLC0415

    cfg = load_config()
    apply_log_level(cfg.logging.level)
    logger.info(
        "Config loaded: model=%s base_url=%s max_iter=%d max_file_kb=%d "
        "memory_persist=%s log_level=%s",
        cfg.llm.model,
        cfg.llm.base_url,
        cfg.agent.max_iterations,
        cfg.agent.max_file_size_kb,
        cfg.memory.persist,
        cfg.logging.level,
    )
    return AgentLoop(cfg)


def run_once(prompt: str) -> None:
    """Run a single prompt and print the result."""
    loop = _build_loop()
    logger.info("Single-shot mode: prompt=%r", prompt[:120])
    answer = loop.run(prompt)
    print(answer)


def run_repl() -> None:
    """Interactive REPL — type 'exit' or Ctrl-C to quit."""
    loop = _build_loop()
    logger.info("REPL mode started")
    print("File Assistant Agent — type your request, or 'exit' to quit.\n")

    while True:
        try:
            prompt = input(">>> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            logger.info("REPL exited by user")
            break

        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit"}:
            print("Bye.")
            logger.info("REPL exited by user command")
            break

        try:
            answer = loop.run(prompt)
            print(answer)
        except Exception as exc:  # noqa: BLE001
            logger.error("REPL error: %s", exc, exc_info=True)
            print(f"Error: {exc}")


def main() -> None:
    args = sys.argv[1:]
    if args:
        run_once(" ".join(args))
    else:
        run_repl()


if __name__ == "__main__":
    main()
