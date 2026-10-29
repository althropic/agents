"""
Unit tests for src/task_queue.py — structured task queue.

The OpenAI client and AgentLoop are fully mocked — no real LLM required.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.task_queue import Task, TaskQueue
from src.agent.memory import Memory
from src.config import AppConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def agent_config(app_config: AppConfig, tmp_workspace: Path) -> AppConfig:
    app_config.workspace = tmp_workspace.resolve()
    app_config.file_access.allowed_roots = ["."]
    return app_config


def _mock_plan_response(tasks: list[str]) -> MagicMock:
    """Build a fake OpenAI completion response returning a JSON plan."""
    msg = MagicMock()
    msg.content = json.dumps(tasks)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_loop(answers: list[str]) -> MagicMock:
    """Build a fake AgentLoop that returns answers in sequence."""
    loop = MagicMock()
    loop.run_with_memory.side_effect = answers
    return loop


# ---------------------------------------------------------------------------
# Task dataclass
# ---------------------------------------------------------------------------

class TestTask:
    def test_defaults(self):
        t = Task(index=1, description="Do something")
        assert t.status == "pending"
        assert t.result == ""

    def test_fields(self):
        t = Task(index=2, description="Do more", result="done", status="done")
        assert t.index == 2
        assert t.description == "Do more"


# ---------------------------------------------------------------------------
# TaskQueue.plan
# ---------------------------------------------------------------------------

class TestTaskQueuePlan:
    def test_parses_json_array(self, agent_config: AppConfig):
        tasks_raw = ["Read config.py", "Add profiles", "Update tests"]
        with patch("src.task_queue.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = (
                _mock_plan_response(tasks_raw)
            )
            queue = TaskQueue(_mock_loop([]), agent_config)
            tasks = queue.plan("Add profile support")

        assert len(tasks) == 3
        assert tasks[0].index == 1
        assert tasks[0].description == "Read config.py"
        assert tasks[0].status == "pending"

    def test_strips_markdown_fences(self, agent_config: AppConfig):
        raw = '```json\n["Task A", "Task B"]\n```'
        msg = MagicMock()
        msg.content = raw
        resp = MagicMock()
        resp.choices = [MagicMock(message=msg)]
        with patch("src.task_queue.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = resp
            queue = TaskQueue(_mock_loop([]), agent_config)
            tasks = queue.plan("Some goal")
        assert len(tasks) == 2
        assert tasks[0].description == "Task A"

    def test_raises_on_invalid_json(self, agent_config: AppConfig):
        msg = MagicMock()
        msg.content = "not valid json"
        resp = MagicMock()
        resp.choices = [MagicMock(message=msg)]
        with patch("src.task_queue.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = resp
            queue = TaskQueue(_mock_loop([]), agent_config)
            with pytest.raises(RuntimeError, match="unparseable"):
                queue.plan("Some goal")

    def test_raises_when_not_a_list(self, agent_config: AppConfig):
        msg = MagicMock()
        msg.content = '{"key": "value"}'
        resp = MagicMock()
        resp.choices = [MagicMock(message=msg)]
        with patch("src.task_queue.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = resp
            queue = TaskQueue(_mock_loop([]), agent_config)
            with pytest.raises(RuntimeError, match="unparseable"):
                queue.plan("Some goal")


# ---------------------------------------------------------------------------
# TaskQueue.run
# ---------------------------------------------------------------------------

class TestTaskQueueRun:
    def _run_queue(
        self,
        agent_config: AppConfig,
        task_descs: list[str],
        answers: list[str],
        memory: Memory | None = None,
    ) -> tuple[list[str], MagicMock]:
        """Helper: mock planner + loop, run queue, return (output, mock_loop)."""
        if memory is None:
            memory = Memory(
                system_prompt="test",
                persist=False,
                export_path=str(agent_config.resolved_memory_export_path()),
            )
        mock_loop = _mock_loop(answers)

        with patch("src.task_queue.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = (
                _mock_plan_response(task_descs)
            )
            queue = TaskQueue(mock_loop, agent_config)
            output = list(queue.run("Test goal", memory))

        return output, mock_loop

    def test_yields_plan_header(self, agent_config: AppConfig):
        output, _ = self._run_queue(
            agent_config, ["Task 1", "Task 2"], ["Result 1", "Result 2"]
        )
        combined = "".join(output)
        assert "Planning" in combined
        assert "Plan (2 tasks)" in combined

    def test_yields_each_task_result(self, agent_config: AppConfig):
        output, _ = self._run_queue(agent_config, ["Task A"], ["The answer"])
        combined = "".join(output)
        assert "Task A" in combined
        assert "The answer" in combined

    def test_calls_loop_for_each_task(self, agent_config: AppConfig):
        _, mock_loop = self._run_queue(
            agent_config, ["Task 1", "Task 2"], ["R1", "R2"]
        )
        assert mock_loop.run_with_memory.call_count == 2

    def test_marks_failed_task_on_exception(self, agent_config: AppConfig):
        memory = Memory(system_prompt="test", persist=False, export_path=".mem")
        mock_loop = MagicMock()
        mock_loop.run_with_memory.side_effect = RuntimeError("boom")

        with patch("src.task_queue.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = (
                _mock_plan_response(["Failing task"])
            )
            queue = TaskQueue(mock_loop, agent_config)
            output = list(queue.run("Goal", memory))

        combined = "".join(output)
        assert "failed" in combined.lower()
        assert "boom" in combined

    def test_summary_counts(self, agent_config: AppConfig):
        output, _ = self._run_queue(
            agent_config, ["T1", "T2", "T3"], ["R1", "R2", "R3"]
        )
        combined = "".join(output)
        assert "3/3" in combined or "3 tasks" in combined

    def test_continues_after_failed_task(self, agent_config: AppConfig):
        """Queue keeps running even when a task fails."""
        mock_loop = MagicMock()
        mock_loop.run_with_memory.side_effect = [
            RuntimeError("fail"),
            "second answer",
        ]
        with patch("src.task_queue.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = (
                _mock_plan_response(["Task 1", "Task 2"])
            )
            queue = TaskQueue(mock_loop, agent_config)
            memory = Memory(system_prompt="test", persist=False, export_path=".mem")
            output = list(queue.run("Goal", memory))

        combined = "".join(output)
        assert "second answer" in combined


# ---------------------------------------------------------------------------
# repl_commands /goal integration
# ---------------------------------------------------------------------------

class TestReplCommandGoal:
    def test_goal_command_runs_queue(self, agent_config: AppConfig):
        """Ensure /goal dispatches to TaskQueue.run."""
        memory = Memory(system_prompt="test", persist=False, export_path=".mem")

        mock_queue_instance = MagicMock()
        mock_queue_instance.run.return_value = iter(["Plan output\n"])

        import src.repl_commands as rc
        # AgentLoop and TaskQueue are lazy local imports inside _handle_goal,
        # so patch them at their source modules.
        with patch("src.agent.loop.AgentLoop"), \
             patch("src.task_queue.TaskQueue", return_value=mock_queue_instance), \
             patch("src.repl_commands.write_output"):
            rc.handle("/goal refactor config.py", agent_config, memory)

        mock_queue_instance.run.assert_called_once()
        goal_arg = mock_queue_instance.run.call_args[0][0]
        assert "refactor config.py" in goal_arg

    def test_goal_missing_description(self, agent_config: AppConfig):
        memory = Memory(system_prompt="test", persist=False, export_path=".mem")
        import src.repl_commands as rc
        with patch("src.repl_commands.write_output") as mock_out:
            rc.handle("/goal", agent_config, memory)
        assert "Usage" in mock_out.call_args[0][0]
