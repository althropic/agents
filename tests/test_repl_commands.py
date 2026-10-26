"""
Unit tests for src/repl_commands.py — REPL slash-command handler.

Tests cover /think, /model, /export, /help, and unknown commands.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.agent.memory import Memory
from src.config import AppConfig
from src import repl_commands


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def cfg(app_config: AppConfig, tmp_workspace: Path) -> AppConfig:
    app_config.workspace = tmp_workspace.resolve()
    app_config.llm.thinking_param = "reasoning_effort"
    app_config.llm.thinking_effort = "high"
    app_config.llm.thinking_budget = 0
    app_config.llm.model = "test-model"
    return app_config


@pytest.fixture()
def mem(cfg: AppConfig) -> Memory:
    return Memory(
        system_prompt="test",
        persist=False,
        export_path=str(cfg.resolved_memory_export_path()),
    )


# ---------------------------------------------------------------------------
# is_command
# ---------------------------------------------------------------------------

class TestIsCommand:
    def test_detects_slash(self):
        assert repl_commands.is_command("/think on") is True

    def test_ignores_plain_prompt(self):
        assert repl_commands.is_command("summarize src/") is False

    def test_empty_string(self):
        assert repl_commands.is_command("") is False


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

class TestHelp:
    def test_returns_true(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output") as mock_out:
            result = repl_commands.handle("/help", cfg, mem)
        assert result is True
        mock_out.assert_called_once()
        assert "/think" in mock_out.call_args[0][0]


# ---------------------------------------------------------------------------
# /think
# ---------------------------------------------------------------------------

class TestThink:
    def test_think_off_disables_effort(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output"):
            repl_commands.handle("/think off", cfg, mem)
        assert cfg.llm.thinking_effort == "none"

    def test_think_on_restores_effort(self, cfg: AppConfig, mem: Memory):
        cfg.llm.thinking_effort = "none"
        with patch("src.repl_commands.write_output"):
            repl_commands.handle("/think on", cfg, mem)
        assert cfg.llm.thinking_effort == "high"

    def test_think_on_keeps_existing_effort(self, cfg: AppConfig, mem: Memory):
        cfg.llm.thinking_effort = "medium"
        with patch("src.repl_commands.write_output"):
            repl_commands.handle("/think on", cfg, mem)
        assert cfg.llm.thinking_effort == "medium"

    def test_think_missing_arg(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output") as mock_out:
            result = repl_commands.handle("/think", cfg, mem)
        assert result is True
        assert "Usage" in mock_out.call_args[0][0]

    def test_think_invalid_arg(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output") as mock_out:
            result = repl_commands.handle("/think maybe", cfg, mem)
        assert result is True
        assert "Usage" in mock_out.call_args[0][0]


# ---------------------------------------------------------------------------
# /think — Anthropic-style token-budget path (thinking_param != reasoning_effort)
# ---------------------------------------------------------------------------

class TestThinkBudget:
    @pytest.fixture()
    def budget_cfg(self, cfg: AppConfig) -> AppConfig:
        cfg.llm.thinking_param = "thinking"
        cfg.llm.thinking_budget = 8192
        return cfg

    def test_off_zeros_budget(self, budget_cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output"):
            repl_commands.handle("/think off", budget_cfg, mem)
        assert budget_cfg.llm.thinking_budget == 0

    def test_on_restores_budget_when_zeroed(self, budget_cfg: AppConfig, mem: Memory):
        budget_cfg.llm.thinking_budget = 0
        with patch("src.repl_commands.write_output"):
            repl_commands.handle("/think on", budget_cfg, mem)
        assert budget_cfg.llm.thinking_budget == 8192

    def test_on_keeps_existing_budget(self, budget_cfg: AppConfig, mem: Memory):
        budget_cfg.llm.thinking_budget = 4096
        with patch("src.repl_commands.write_output"):
            repl_commands.handle("/think on", budget_cfg, mem)
        assert budget_cfg.llm.thinking_budget == 4096


# ---------------------------------------------------------------------------
# /model
# ---------------------------------------------------------------------------

class TestModel:
    def test_switches_model(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output"):
            repl_commands.handle("/model new-model-v2", cfg, mem)
        assert cfg.llm.model == "new-model-v2"

    def test_no_arg_shows_current(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output") as mock_out:
            repl_commands.handle("/model", cfg, mem)
        output = mock_out.call_args[0][0]
        assert "test-model" in output

    def test_returns_true(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output"):
            result = repl_commands.handle("/model x", cfg, mem)
        assert result is True


# ---------------------------------------------------------------------------
# /export
# ---------------------------------------------------------------------------

class TestExport:
    def test_creates_markdown_file(
        self, cfg: AppConfig, mem: Memory, tmp_workspace: Path
    ):
        mem.add({"role": "user", "content": "hello"})
        mem.add({"role": "assistant", "content": "hi there"})

        with patch("src.repl_commands.write_output"):
            repl_commands.handle("/export mysession", cfg, mem)

        export_dir = cfg.resolved_memory_export_path()
        md_file = export_dir / "mysession.md"
        assert md_file.exists()
        content = md_file.read_text(encoding="utf-8")
        assert "hello" in content
        assert "hi there" in content

    def test_export_no_label(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output") as mock_out:
            repl_commands.handle("/export", cfg, mem)
        assert mock_out.called
        assert "→" in mock_out.call_args[0][0]

    def test_returns_true(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output"):
            result = repl_commands.handle("/export", cfg, mem)
        assert result is True


# ---------------------------------------------------------------------------
# Unknown command
# ---------------------------------------------------------------------------

class TestUnknownCommand:
    def test_returns_true_for_unknown(self, cfg: AppConfig, mem: Memory):
        with patch("src.repl_commands.write_output") as mock_out:
            result = repl_commands.handle("/nonexistent", cfg, mem)
        assert result is True
        assert "Unknown" in mock_out.call_args[0][0]
