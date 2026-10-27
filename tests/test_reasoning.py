"""
Unit tests for src/agent/reasoning.py — extract_reasoning().

Covers the field-name variants servers use for the chain-of-thought and
confirms content is never mistaken for reasoning.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.agent.reasoning import extract_reasoning


def _delta(**kw) -> SimpleNamespace:
    return SimpleNamespace(**kw)


class TestExtractReasoning:
    def test_reasoning_field(self):
        assert extract_reasoning(_delta(reasoning="thinking...")) == "thinking..."

    def test_reasoning_content_field(self):
        assert extract_reasoning(_delta(reasoning_content="cot")) == "cot"

    def test_thinking_field(self):
        assert extract_reasoning(_delta(thinking="hmm")) == "hmm"

    def test_none_when_absent(self):
        assert extract_reasoning(_delta(content="answer")) is None

    def test_returns_reasoning_not_content(self):
        d = _delta(content="answer", reasoning="thought")
        assert extract_reasoning(d) == "thought"

    def test_first_candidate_wins(self):
        d = _delta(reasoning="r", reasoning_content="rc", thinking="t")
        assert extract_reasoning(d) == "r"

    def test_empty_string_treated_as_absent(self):
        assert extract_reasoning(_delta(reasoning="")) is None
