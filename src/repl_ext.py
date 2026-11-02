"""
Extended REPL command handlers — separated from repl_commands.py to keep
both files under the 200-line limit.

Handlers here are the "heavy" ones that import optional subsystems
(task queue, orchestrator, vector memory) at call time via lazy imports.
"""

from __future__ import annotations

from src.agent.memory import Memory
from src.config import AppConfig
from src.io import write_output
from src.logger import get_logger

logger = get_logger(__name__)


def handle_goal(goal: str, cfg: AppConfig, memory: Memory) -> bool:
    """Run a goal through the structured task queue."""
    if not goal:
        write_output("Usage: /goal <description of what you want to achieve>")
        return True
    from src.agent.loop import AgentLoop  # noqa: PLC0415
    from src.task_queue import TaskQueue  # noqa: PLC0415

    loop = AgentLoop(cfg)
    queue = TaskQueue(loop, cfg)
    try:
        for event in queue.run(goal, memory):
            write_output(event, end="")
    except Exception as exc:  # noqa: BLE001
        logger.error("/goal failed: %s", exc, exc_info=True)
        write_output(f"\nError: {exc}")
    return True


def handle_orchestrate(goal: str, cfg: AppConfig, memory: Memory) -> bool:
    """Run a goal through the multi-agent orchestrator."""
    if not goal:
        write_output("Usage: /orchestrate <description of what you want to achieve>")
        return True
    if not cfg.orchestrator.enabled:
        write_output(
            "Orchestrator is disabled. Set orchestrator.enabled: true in config.yaml."
        )
        logger.warning("/orchestrate: disabled in config")
        return True

    from src.orchestrator import Orchestrator  # noqa: PLC0415

    orch = Orchestrator(cfg)
    try:
        for event in orch.run(goal, memory):
            write_output(event, end="")
    except Exception as exc:  # noqa: BLE001
        logger.error("/orchestrate failed: %s", exc, exc_info=True)
        write_output(f"\nError: {exc}")
    return True


def handle_index(cfg: AppConfig) -> bool:
    """Build (or rebuild) the vector memory index from the workspace."""
    if not cfg.vector_memory.enabled:
        write_output(
            "Vector memory is disabled. "
            "Set vector_memory.enabled: true in config.yaml."
        )
        logger.warning("/index: vector_memory disabled")
        return True

    from src.memory_store import VectorMemory  # noqa: PLC0415

    index_path = cfg.resolved_index_path()
    store = VectorMemory(index_path)
    roots = cfg.resolved_roots()
    write_output(f"Indexing {len(roots)} root(s)…")
    logger.info("/index: indexing roots=%s", roots)

    count = store.index_workspace(roots, cfg.vector_memory.max_file_size_kb)
    store.save()
    cfg._vector_memory = store  # noqa: SLF001

    write_output(f"Index built: {count} files → {index_path}")
    logger.info("/index: done count=%d path=%s", count, index_path)
    return True
