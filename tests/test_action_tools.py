"""
Unit tests for src/agent/action_tools.py — shell, git, and test tools.

All tests use tmp_workspace (conftest.py) so no real project files are touched.
Git tests initialise a fresh repo inside the temp directory.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from src.agent.action_tools import (
    build_action_tool_map,
    git_commit,
    git_diff,
    git_status,
    run_command,
    run_tests,
)
from src.agent.tools import build_tool_map


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

ALLOWED = ["pytest", "python", "git", "echo"]
TIMEOUT = 10


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def git_workspace(tmp_workspace: Path) -> Path:
    """tmp_workspace with a fresh git repo and one committed file."""
    subprocess.run(
        ["git", "init"], cwd=str(tmp_workspace),
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_workspace), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(tmp_workspace), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "add", "-A"], cwd=str(tmp_workspace),
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=str(tmp_workspace),
        capture_output=True, check=True,
    )
    return tmp_workspace


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------

class TestRunCommand:
    def test_allowed_command(self, tmp_workspace: Path):
        result = run_command(
            "echo hello", None, ALLOWED, tmp_workspace, TIMEOUT
        )
        assert "Exit code: 0" in result
        assert "hello" in result

    def test_rejects_disallowed_command(self, tmp_workspace: Path):
        with pytest.raises(PermissionError, match="not in the allowed"):
            run_command(
                "whoami", None, ALLOWED, tmp_workspace, TIMEOUT
            )

    def test_cwd_relative(self, tmp_workspace: Path):
        sub = tmp_workspace / "subdir"
        sub.mkdir(exist_ok=True)
        result = run_command(
            "echo test", "subdir", ALLOWED, tmp_workspace, TIMEOUT
        )
        assert "Exit code: 0" in result

    def test_rejects_cwd_outside_workspace(self, tmp_workspace: Path, tmp_path: Path):
        outside = tmp_path.parent
        with pytest.raises(PermissionError, match="outside workspace"):
            run_command(
                "echo test", str(outside), ALLOWED, tmp_workspace, TIMEOUT
            )

    def test_timeout(self, tmp_workspace: Path):
        result = run_command(
            f'{sys.executable} -c "import time; time.sleep(5)"',
            None, ["python"], tmp_workspace, 1,
        )
        assert "Timeout" in result

    def test_empty_command(self, tmp_workspace: Path):
        with pytest.raises(PermissionError):
            run_command("", None, ALLOWED, tmp_workspace, TIMEOUT)


# ---------------------------------------------------------------------------
# git_status
# ---------------------------------------------------------------------------

class TestGitStatus:
    def test_clean_repo(self, git_workspace: Path):
        result = git_status(git_workspace, ALLOWED, TIMEOUT)
        assert "Exit code: 0" in result

    def test_shows_modified_file(self, git_workspace: Path):
        (git_workspace / "hello.txt").write_text("modified", encoding="utf-8")
        result = git_status(git_workspace, ALLOWED, TIMEOUT)
        assert "hello.txt" in result

    def test_rejects_when_git_not_allowed(self, git_workspace: Path):
        with pytest.raises(PermissionError, match="git"):
            git_status(git_workspace, ["pytest"], TIMEOUT)


# ---------------------------------------------------------------------------
# git_diff
# ---------------------------------------------------------------------------

class TestGitDiff:
    def test_unstaged_diff(self, git_workspace: Path):
        (git_workspace / "hello.txt").write_text("changed", encoding="utf-8")
        result = git_diff(False, git_workspace, ALLOWED, TIMEOUT)
        assert "Exit code: 0" in result
        assert "changed" in result

    def test_staged_diff(self, git_workspace: Path):
        f = git_workspace / "hello.txt"
        f.write_text("staged change", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-A"], cwd=str(git_workspace),
            capture_output=True, check=True,
        )
        result = git_diff(True, git_workspace, ALLOWED, TIMEOUT)
        assert "Exit code: 0" in result
        assert "staged change" in result

    def test_no_changes(self, git_workspace: Path):
        result = git_diff(False, git_workspace, ALLOWED, TIMEOUT)
        assert "Exit code: 0" in result

    def test_rejects_when_git_not_allowed(self, git_workspace: Path):
        with pytest.raises(PermissionError):
            git_diff(False, git_workspace, ["pytest"], TIMEOUT)


# ---------------------------------------------------------------------------
# git_commit
# ---------------------------------------------------------------------------

class TestGitCommit:
    def test_commits_changes(self, git_workspace: Path):
        (git_workspace / "new.txt").write_text("new file", encoding="utf-8")
        result = git_commit("add new file", git_workspace, ALLOWED, TIMEOUT)
        assert "Exit code: 0" in result

        # Verify the commit happened
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=str(git_workspace),
            capture_output=True, text=True, check=True,
        )
        assert "add new file" in log.stdout

    def test_rejects_when_git_not_allowed(self, git_workspace: Path):
        with pytest.raises(PermissionError):
            git_commit("msg", git_workspace, ["pytest"], TIMEOUT)


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------

class TestRunTests:
    def test_runs_passing_tests(self, tmp_workspace: Path):
        test_file = tmp_workspace / "test_sample.py"
        test_file.write_text(
            "def test_ok():\n    assert True\n", encoding="utf-8"
        )
        result = run_tests(None, tmp_workspace, ALLOWED, 30)
        assert "Exit code: 0" in result
        assert "passed" in result

    def test_runs_with_args(self, tmp_workspace: Path):
        test_file = tmp_workspace / "test_sample.py"
        test_file.write_text(
            "def test_ok():\n    assert True\n", encoding="utf-8"
        )
        result = run_tests("-q --no-header", tmp_workspace, ALLOWED, 30)
        assert "Exit code: 0" in result

    def test_rejects_when_pytest_not_allowed(self, tmp_workspace: Path):
        with pytest.raises(PermissionError, match="pytest"):
            run_tests(None, tmp_workspace, ["git"], 30)


# ---------------------------------------------------------------------------
# build_action_tool_map
# ---------------------------------------------------------------------------

class TestBuildActionToolMap:
    def test_all_keys_present(self, tmp_workspace: Path):
        tool_map = build_action_tool_map(ALLOWED, tmp_workspace, TIMEOUT)
        assert set(tool_map.keys()) == {
            "run_command", "git_status", "git_diff",
            "git_commit", "run_tests",
        }

    def test_run_command_via_map(self, tmp_workspace: Path):
        tool_map = build_action_tool_map(ALLOWED, tmp_workspace, TIMEOUT)
        result = tool_map["run_command"](command="echo via_map")
        assert "via_map" in result

    def test_git_status_via_map(self, git_workspace: Path):
        tool_map = build_action_tool_map(ALLOWED, git_workspace, TIMEOUT)
        result = tool_map["git_status"]()
        assert "Exit code: 0" in result


# ---------------------------------------------------------------------------
# build_tool_map integration (file + action tools combined)
# ---------------------------------------------------------------------------

class TestBuildToolMapIntegration:
    def test_file_only_without_action_params(self, tmp_workspace: Path):
        """Without allowed_commands/workspace, only file tools are present."""
        tool_map = build_tool_map([tmp_workspace.resolve()])
        assert set(tool_map.keys()) == {
            "read_file", "write_file", "list_dir", "search_files", "grep",
        }

    def test_full_map_with_action_tools(self, tmp_workspace: Path):
        """With allowed_commands and workspace, action tools are included."""
        tool_map = build_tool_map(
            [tmp_workspace.resolve()],
            allowed_commands=ALLOWED,
            workspace=tmp_workspace,
            command_timeout=TIMEOUT,
        )
        assert "run_command" in tool_map
        assert "git_status" in tool_map
        assert "run_tests" in tool_map
        assert "read_file" in tool_map
