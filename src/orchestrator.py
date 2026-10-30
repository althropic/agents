"""
Orchestrator — coordinates specialist sub-agents to complete a multi-step goal.

The orchestrator:
1. Uses the task queue to break the goal into subtasks.
2. Assigns each subtask to the most appropriate specialist role
   (researcher / coder / reviewer / tester) via a routing LLM call.
3. Instantiates a scoped AgentLoop for that role (restricted tools,
   specialist system prompt) and runs the subtask against shared memory.
4. Yields progress strings so the REPL can stream results incrementally.

Usage (from repl_commands.py):
    orch = Orchestrator(cfg)
    for event in orch.run(goal, memory):
        write_output(event)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from openai import OpenAI

from src.agent.loop import AgentLoop
from src.agent.memory import Memory
from src.agent.profiles import get_profile
from src.logger import get_logger
from src.orchestrator_helpers import _build_scoped_loop, _route_task
from src.task_queue import TaskQueue

if TYPE_CHECKING:
    from src.config import AppConfig

logger = get_logger(__name__)


class Orchestrator:
    """Plans a goal as subtasks and dispatches each to a specialist sub-agent."""

    def __init__(self, cfg: "AppConfig") -> None:
        self._cfg = cfg
        self._client = OpenAI(
            base_url=cfg.llm.base_url,
            api_key=cfg.llm.api_key,
        )
        logger.info(
            "Orchestrator ready: model=%s workspace=%s",
            cfg.llm.model,
            cfg.workspace,
        )

    def run(self, goal: str, memory: Memory) -> Iterator[str]:
        """Plan *goal*, route each subtask to a specialist, and yield progress."""
        yield f"\n🎯 Orchestrating: {goal}\n"
        logger.info("Orchestrator.run: goal=%r", goal[:120])

        coordinator_loop = AgentLoop(self._cfg)
        queue = TaskQueue(coordinator_loop, self._cfg)
        try:
            tasks = queue.plan(goal)
        except RuntimeError as exc:
            yield f"✗ Planning failed: {exc}\n"
            logger.error("Orchestrator: planning failed: %s", exc)
            return

        yield f"Plan ({len(tasks)} tasks):\n"
        for t in tasks:
            yield f"  [{t.index}] {t.description}\n"
        yield "\n"

        for task in tasks:
            role = _route_task(task.description, self._client, self._cfg.llm.model)
            profile = get_profile(role)

            task.status = "running"
            yield f"▶ [{task.index}/{len(tasks)}] [{profile.name}] {task.description}\n"
            logger.info(
                "Orchestrator: task %d/%d role=%s: %r",
                task.index, len(tasks), role, task.description,
            )

            scoped_loop = _build_scoped_loop(self._cfg, profile)
            try:
                result = scoped_loop.run_with_memory(task.description, memory)
                task.result = result
                task.status = "done"
                yield f"{result}\n"
                yield f"✓ Task {task.index} done [{profile.name}].\n\n"
                logger.info("Orchestrator: task %d done", task.index)
            except Exception as exc:  # noqa: BLE001
                task.status = "failed"
                task.result = str(exc)
                yield f"✗ Task {task.index} failed [{profile.name}]: {exc}\n\n"
                logger.error(
                    "Orchestrator: task %d failed: %s", task.index, exc, exc_info=True
                )

        done = sum(1 for t in tasks if t.status == "done")
        failed = sum(1 for t in tasks if t.status == "failed")
        yield f"Done: {done}/{len(tasks)} tasks completed"
        if failed:
            yield f", {failed} failed"
        yield ".\n"
        logger.info(
            "Orchestrator: goal complete — %d done, %d failed", done, failed
        )
