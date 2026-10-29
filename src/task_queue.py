"""
Structured task queue for goal-level planning.

The user describes a high-level goal; the planner LLM breaks it into an
ordered list of subtasks; each subtask is executed in sequence by the
existing AgentLoop, with progress reported after every step.

Usage (from runner.py / repl_commands.py):
    queue = TaskQueue(loop, cfg)
    for event in queue.run(goal, memory):
        write_output(event)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator, List

from openai import OpenAI

from src.logger import get_logger

if TYPE_CHECKING:
    from src.agent.loop import AgentLoop
    from src.agent.memory import Memory
    from src.config import AppConfig

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class Task:
    index: int
    description: str
    result: str = ""
    status: str = "pending"   # pending | running | done | failed


# ---------------------------------------------------------------------------
# Planner prompt
# ---------------------------------------------------------------------------

_PLAN_SYSTEM = (
    "You are a planning assistant. When given a goal, respond with ONLY a "
    "JSON array of short task descriptions (strings) in the order they should "
    "be executed. No markdown fences, no explanation — just the JSON array. "
    "Example: [\"Read config.py\", \"Add profile support\", \"Update tests\"]"
)


def _build_plan_messages(goal: str, planner_prompt: str) -> list:
    system = planner_prompt or _PLAN_SYSTEM
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Goal: {goal}"},
    ]


# ---------------------------------------------------------------------------
# TaskQueue
# ---------------------------------------------------------------------------

class TaskQueue:
    """Plans and executes a goal as a sequence of subtasks."""

    def __init__(self, loop: "AgentLoop", cfg: "AppConfig") -> None:
        self._loop = loop
        self._cfg = cfg

    def plan(self, goal: str) -> List[Task]:
        """Ask the LLM to break *goal* into subtasks. Returns a Task list."""
        client = OpenAI(
            base_url=self._cfg.llm.base_url,
            api_key=self._cfg.llm.api_key,
        )
        messages = _build_plan_messages(goal, self._cfg.agent.planner_prompt)
        logger.info("TaskQueue.plan: goal=%r", goal[:120])

        response = client.chat.completions.create(
            model=self._cfg.llm.model,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )
        raw = (response.choices[0].message.content or "").strip()
        logger.debug("TaskQueue.plan: raw=%r", raw[:300])

        # Strip markdown fences if the model ignored instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            items = json.loads(raw)
            if not isinstance(items, list):
                raise ValueError("Expected a JSON array")
            tasks = [
                Task(index=i + 1, description=str(d))
                for i, d in enumerate(items)
            ]
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("TaskQueue.plan: failed to parse plan: %s — raw=%r", exc, raw[:300])
            raise RuntimeError(
                f"Planner returned an unparseable response: {exc}\n\nRaw: {raw[:300]}"
            ) from exc

        logger.info("TaskQueue.plan: %d tasks", len(tasks))
        return tasks

    def run(self, goal: str, memory: "Memory") -> Iterator[str]:
        """Plan *goal* and execute each task, yielding progress strings."""
        yield f"\n📋 Planning: {goal}\n"

        tasks = self.plan(goal)

        yield f"Plan ({len(tasks)} tasks):\n"
        for t in tasks:
            yield f"  [{t.index}] {t.description}\n"
        yield "\n"

        for task in tasks:
            task.status = "running"
            yield f"▶ [{task.index}/{len(tasks)}] {task.description}\n"
            logger.info(
                "TaskQueue: executing task %d/%d: %r",
                task.index, len(tasks), task.description,
            )

            try:
                result = self._loop.run_with_memory(task.description, memory)
                task.result = result
                task.status = "done"
                yield f"{result}\n"
                yield f"✓ Task {task.index} done.\n\n"
                logger.info("TaskQueue: task %d done", task.index)
            except Exception as exc:  # noqa: BLE001
                task.status = "failed"
                task.result = str(exc)
                yield f"✗ Task {task.index} failed: {exc}\n\n"
                logger.error(
                    "TaskQueue: task %d failed: %s", task.index, exc, exc_info=True
                )

        done = sum(1 for t in tasks if t.status == "done")
        failed = sum(1 for t in tasks if t.status == "failed")
        yield f"Done: {done}/{len(tasks)} tasks completed"
        if failed:
            yield f", {failed} failed"
        yield ".\n"
        logger.info(
            "TaskQueue: goal complete — %d done, %d failed", done, failed
        )
