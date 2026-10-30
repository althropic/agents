"""
Tests for the orchestrator layer:
  - src/agent/profiles.py   (AgentProfile registry)
  - src/orchestrator.py     (Orchestrator, _route_task, _build_scoped_loop)
  - src/repl_commands.py    (/orchestrate command)

No live LLM is required — the OpenAI client and task-queue planner are fully
mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent.memory import Memory
from src.agent.profiles import PROFILES, AgentProfile, get_profile
from src.config import AppConfig
from src import repl_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_completion(content: str):
    """Minimal fake OpenAI completion object."""
    msg = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def _final_answer_loop(answer: str):
    """
    Return a mock AgentLoop.run_with_memory that always returns *answer*
    without touching any files.
    """
    mock = MagicMock()
    mock.return_value = answer
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def cfg(app_config: AppConfig, tmp_workspace: Path) -> AppConfig:
    app_config.workspace = tmp_workspace.resolve()
    app_config.file_access.allowed_roots = ["."]
    app_config.orchestrator.enabled = True
    return app_config


@pytest.fixture()
def mem(cfg: AppConfig) -> Memory:
    return Memory(
        system_prompt="test",
        persist=False,
        export_path=str(cfg.resolved_memory_export_path()),
    )


# ---------------------------------------------------------------------------
# profiles.py tests
# ---------------------------------------------------------------------------

class TestProfiles:
    def test_all_builtin_roles_present(self):
        for role in ("researcher", "coder", "reviewer", "tester"):
            assert role in PROFILES

    def test_get_profile_known(self):
        p = get_profile("coder")
        assert isinstance(p, AgentProfile)
        assert p.name == "coder"

    def test_get_profile_case_insensitive(self):
        assert get_profile("RESEARCHER").name == "researcher"

    def test_get_profile_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown role"):
            get_profile("wizard")

    def test_researcher_has_no_write_tool(self):
        profile = get_profile("researcher")
        assert "write_file" not in profile.allowed_tools

    def test_reviewer_has_no_write_tool(self):
        profile = get_profile("reviewer")
        assert "write_file" not in profile.allowed_tools

    def test_coder_has_write_tool(self):
        profile = get_profile("coder")
        assert "write_file" in profile.allowed_tools

    def test_tester_has_run_tests(self):
        profile = get_profile("tester")
        assert "run_tests" in profile.allowed_tools


# ---------------------------------------------------------------------------
# _route_task tests
# ---------------------------------------------------------------------------

class TestRouteTask:
    def test_routes_via_llm_response(self, cfg):
        from src.orchestrator_helpers import _route_task

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_completion("coder")

        role = _route_task("Write a utility function", mock_client, cfg.llm.model)
        assert role == "coder"

    def test_falls_back_to_keyword_on_unknown_llm_role(self, cfg):
        from src.orchestrator_helpers import _route_task

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_completion("overlord")

        role = _route_task("write a new module", mock_client, cfg.llm.model)
        assert role == "coder"

    def test_falls_back_to_keyword_on_llm_error(self, cfg):
        from src.orchestrator_helpers import _route_task

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("network error")

        role = _route_task("run the test suite", mock_client, cfg.llm.model)
        assert role == "tester"

    def test_defaults_to_researcher_when_no_keyword_matches(self, cfg):
        from src.orchestrator_helpers import _route_task

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_completion("??")

        role = _route_task("do something unspecified", mock_client, cfg.llm.model)
        assert role == "researcher"

    @pytest.mark.parametrize("desc,expected", [
        ("search for all TODO comments", "researcher"),
        ("implement the login handler", "coder"),
        ("audit the auth module for security issues", "reviewer"),
        ("run tests and report failures", "tester"),
    ])
    def test_keyword_routing(self, cfg, desc, expected):
        from src.orchestrator_helpers import _route_task

        mock_client = MagicMock()
        # Return something invalid to force keyword fallback
        mock_client.chat.completions.create.return_value = _fake_completion("invalid")

        role = _route_task(desc, mock_client, cfg.llm.model)
        assert role == expected


# ---------------------------------------------------------------------------
# _build_scoped_loop tests
# ---------------------------------------------------------------------------

class TestBuildScopedLoop:
    def test_scoped_loop_uses_profile_system_prompt(self, cfg):
        from src.orchestrator_helpers import _build_scoped_loop
        profile = get_profile("reviewer")

        with patch("src.agent.loop.OpenAI"):
            loop = _build_scoped_loop(cfg, profile)

        assert loop._cfg.agent.system_prompt == profile.system_prompt  # noqa: SLF001

    def test_scoped_loop_restricts_tool_map(self, cfg):
        from src.orchestrator_helpers import _build_scoped_loop
        profile = get_profile("reviewer")  # read_file, list_dir, search_files, grep only

        with patch("src.agent.loop.OpenAI"):
            loop = _build_scoped_loop(cfg, profile)

        # All keys in the loop's tool_map must be in the allowed list
        assert set(loop._tool_map).issubset(set(profile.allowed_tools))  # noqa: SLF001

    def test_scoped_loop_does_not_mutate_original_cfg(self, cfg):
        from src.orchestrator_helpers import _build_scoped_loop
        original_prompt = cfg.agent.system_prompt
        profile = get_profile("coder")

        with patch("src.agent.loop.OpenAI"):
            _build_scoped_loop(cfg, profile)

        assert cfg.agent.system_prompt == original_prompt


# ---------------------------------------------------------------------------
# Orchestrator.run tests
# ---------------------------------------------------------------------------

class TestOrchestratorRun:
    def _plan_return(self, tasks: list[str]):
        """Fake TaskQueue.plan return value from a list of task strings."""
        from src.task_queue import Task
        return [Task(index=i + 1, description=d) for i, d in enumerate(tasks)]

    def test_run_yields_plan_header(self, cfg, mem):
        from src.orchestrator import Orchestrator

        plan = self._plan_return(["Read the docs"])

        with (
            patch("src.orchestrator.OpenAI"),
            patch("src.orchestrator.TaskQueue.plan", return_value=plan),
            patch("src.orchestrator._route_task", return_value="researcher"),
            patch("src.orchestrator._build_scoped_loop") as mock_build,
        ):
            mock_loop = MagicMock()
            mock_loop.run_with_memory = MagicMock(return_value="done")
            mock_build.return_value = mock_loop

            orch = Orchestrator(cfg)
            events = list(orch.run("some goal", mem))

        header = "".join(events)
        assert "Orchestrating" in header
        assert "Plan" in header

    def test_run_executes_all_tasks(self, cfg, mem):
        from src.orchestrator import Orchestrator

        plan = self._plan_return(["Task A", "Task B", "Task C"])

        with (
            patch("src.orchestrator.OpenAI"),
            patch("src.orchestrator.TaskQueue.plan", return_value=plan),
            patch("src.orchestrator._route_task", return_value="coder"),
            patch("src.orchestrator._build_scoped_loop") as mock_build,
        ):
            mock_loop = MagicMock()
            mock_loop.run_with_memory = MagicMock(side_effect=["res A", "res B", "res C"])
            mock_build.return_value = mock_loop

            orch = Orchestrator(cfg)
            events = list(orch.run("some goal", mem))

        assert mock_loop.run_with_memory.call_count == 3
        full = "".join(events)
        assert "3/3" in full or "3 tasks" in full

    def test_run_handles_planning_failure_gracefully(self, cfg, mem):
        from src.orchestrator import Orchestrator

        with (
            patch("src.orchestrator.OpenAI"),
            patch("src.orchestrator.AgentLoop"),
            patch("src.orchestrator.TaskQueue.plan",
                  side_effect=RuntimeError("bad plan")),
        ):
            orch = Orchestrator(cfg)
            events = list(orch.run("some goal", mem))

        full = "".join(events)
        assert "failed" in full.lower() or "Planning failed" in full

    def test_run_handles_task_failure_gracefully(self, cfg, mem):
        from src.orchestrator import Orchestrator

        plan = self._plan_return(["Task A"])

        with (
            patch("src.orchestrator.OpenAI"),
            patch("src.orchestrator.TaskQueue.plan", return_value=plan),
            patch("src.orchestrator._route_task", return_value="coder"),
            patch("src.orchestrator._build_scoped_loop") as mock_build,
        ):
            mock_loop = MagicMock()
            mock_loop.run_with_memory.side_effect = RuntimeError("tool error")
            mock_build.return_value = mock_loop

            orch = Orchestrator(cfg)
            events = list(orch.run("some goal", mem))

        full = "".join(events)
        assert "failed" in full.lower()

    def test_run_includes_role_label_in_output(self, cfg, mem):
        from src.orchestrator import Orchestrator

        plan = self._plan_return(["Inspect the tests"])

        with (
            patch("src.orchestrator.OpenAI"),
            patch("src.orchestrator.TaskQueue.plan", return_value=plan),
            patch("src.orchestrator._route_task", return_value="tester"),
            patch("src.orchestrator._build_scoped_loop") as mock_build,
        ):
            mock_loop = MagicMock()
            mock_loop.run_with_memory.return_value = "tests passed"
            mock_build.return_value = mock_loop

            orch = Orchestrator(cfg)
            events = list(orch.run("run all tests", mem))

        full = "".join(events)
        assert "tester" in full


# ---------------------------------------------------------------------------
# /orchestrate slash command tests
# ---------------------------------------------------------------------------

class TestOrchestrateCommand:
    def test_disabled_by_default(self, cfg, mem):
        cfg.orchestrator.enabled = False
        captured = []
        with patch("src.io.sys") as mock_sys:
            mock_sys.stdout.write = lambda t: captured.append(t)
            result = repl_commands.handle("/orchestrate fix the tests", cfg, mem)
        assert result is True
        assert any("disabled" in s.lower() for s in captured)

    def test_empty_goal_prints_usage(self, cfg, mem):
        cfg.orchestrator.enabled = True
        captured = []
        with patch("src.io.sys") as mock_sys:
            mock_sys.stdout.write = lambda t: captured.append(t)
            result = repl_commands.handle("/orchestrate", cfg, mem)
        assert result is True
        assert any("Usage" in s for s in captured)

    def test_orchestrate_runs_orchestrator(self, cfg, mem):
        cfg.orchestrator.enabled = True
        with patch("src.repl_commands._handle_orchestrate") as mock_handler:
            mock_handler.return_value = True
            result = repl_commands.handle("/orchestrate refactor config.py", cfg, mem)
        mock_handler.assert_called_once()
        assert result is True

    def test_help_lists_orchestrate(self, cfg, mem):
        captured = []
        with patch("src.io.sys") as mock_sys:
            mock_sys.stdout.write = lambda t: captured.append(t)
            repl_commands.handle("/help", cfg, mem)
        full = "".join(captured)
        assert "/orchestrate" in full
