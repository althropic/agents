"""
Unit tests for src/config.py — LLMConfig thinking/extra_body handling.

These guard the reasoning_effort regression: Ollama's `reasoning_effort` is a
string enum (none|low|medium|high|max), so the value sent for it must never be
an integer token budget.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import LLMConfig


def _llm(**overrides) -> LLMConfig:
    base: dict = {"base_url": "http://localhost:8080/v1", "model": "nemotron-3-ultra"}
    base.update(overrides)
    return LLMConfig(**base)


class TestThinkingExtraBody:
    def test_reasoning_effort_sends_string_enum(self):
        cfg = _llm(thinking_param="reasoning_effort", thinking_effort="high")
        extra = cfg.thinking_extra_body()
        assert extra == {"reasoning_effort": "high"}
        # Regression guard: the value must be a string, never an int.
        assert isinstance(extra["reasoning_effort"], str)

    def test_reasoning_effort_none_sent_explicitly(self):
        # "none" is sent (not omitted) so the server actually disables thinking.
        cfg = _llm(thinking_param="reasoning_effort", thinking_effort="none")
        assert cfg.thinking_extra_body() == {"reasoning_effort": "none"}

    def test_reasoning_effort_each_level(self):
        for level in ("none", "low", "medium", "high", "max"):
            cfg = _llm(thinking_effort=level)
            assert cfg.thinking_extra_body() == {"reasoning_effort": level}

    def test_thinking_budget_path_sends_int(self):
        cfg = _llm(thinking_param="thinking", thinking_budget=4096)
        extra = cfg.thinking_extra_body()
        assert extra == {"thinking": 4096}
        assert isinstance(extra["thinking"], int)

    def test_thinking_budget_zero_omits_extra_body(self):
        cfg = _llm(thinking_param="thinking", thinking_budget=0)
        assert cfg.thinking_extra_body() is None

    def test_invalid_effort_rejected(self):
        # A token count is not a valid effort level and must fail at load time.
        with pytest.raises(ValidationError):
            _llm(thinking_effort="8192")
