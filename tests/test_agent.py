"""
Integration tests for the ReAct agent loop (src/agent/loop.py).

The OpenAI client is fully mocked — no real LLM endpoint is required.
Scenarios tested:
  1. Single-turn: model returns a final answer with no tool calls.
  2. Tool-use turn: model returns a tool call, loop executes it, model
     then returns a final answer.
  3. Max-iterations guard: model keeps calling tools forever → RuntimeError.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

from src.agent.loop import AgentLoop
from src.agent.memory import Memory
from src.config import AppConfig


# ---------------------------------------------------------------------------
# Helpers to build fake OpenAI response objects
# ---------------------------------------------------------------------------

def _make_message(content: str | None, tool_calls: list | None = None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    # model_dump used when appending assistant tool-call messages to memory
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in (tool_calls or [])
        ],
    }
    return msg


def _make_tool_call(call_id: str, name: str, arguments: str):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def _make_response(message):
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Fixture: AppConfig pointing at tmp_workspace
# ---------------------------------------------------------------------------

@pytest.fixture()
def agent_config(app_config: AppConfig, tmp_workspace: Path) -> AppConfig:
    """Return the test AppConfig with allowed_roots overridden to tmp_workspace."""
    app_config.file_access.allowed_roots = [str(tmp_workspace)]
    return app_config


# ---------------------------------------------------------------------------
# Test: single-turn final answer (no tools)
# ---------------------------------------------------------------------------

class TestSingleTurnAnswer:
    def test_returns_final_answer(self, agent_config: AppConfig):
        final_msg = _make_message("The answer is 42.")
        mock_response = _make_response(final_msg)

        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.return_value = mock_response

            loop = AgentLoop(agent_config)
            result = loop.run("What is 6 times 7?")

        assert result == "The answer is 42."
        assert mock_client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# Test: one tool call then final answer
# ---------------------------------------------------------------------------

class TestToolCallThenAnswer:
    def test_executes_tool_and_returns_answer(
        self, agent_config: AppConfig, tmp_workspace: Path
    ):
        import json

        hello_path = str(tmp_workspace / "hello.txt")

        tool_call = _make_tool_call(
            call_id="call_1",
            name="read_file",
            arguments=json.dumps({"path": hello_path}),
        )
        tool_msg = _make_message(None, tool_calls=[tool_call])
        tool_response = _make_response(tool_msg)

        final_msg = _make_message("The file says: Hello, world!")
        final_response = _make_response(final_msg)

        responses = iter([tool_response, final_response])

        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.side_effect = lambda **kw: next(responses)

            loop = AgentLoop(agent_config)
            result = loop.run(f"Read the file at {hello_path}")

        assert result == "The file says: Hello, world!"
        assert mock_client.chat.completions.create.call_count == 2

        # Verify the tool result was fed back: last call's messages should
        # contain a 'tool' role entry with the file contents.
        last_call_messages = (
            mock_client.chat.completions.create.call_args_list[-1].kwargs["messages"]
        )
        tool_results = [m for m in last_call_messages if m.get("role") == "tool"]
        assert len(tool_results) == 1
        assert "Hello, world!" in tool_results[0]["content"]


# ---------------------------------------------------------------------------
# Test: unknown tool name → error result, loop continues
# ---------------------------------------------------------------------------

class TestUnknownTool:
    def test_unknown_tool_does_not_crash_loop(self, agent_config: AppConfig):
        import json

        tool_call = _make_tool_call(
            call_id="call_x",
            name="nonexistent_tool",
            arguments=json.dumps({}),
        )
        tool_msg = _make_message(None, tool_calls=[tool_call])
        tool_response = _make_response(tool_msg)
        final_response = _make_response(_make_message("Done despite error."))

        responses = iter([tool_response, final_response])

        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.side_effect = lambda **kw: next(responses)

            loop = AgentLoop(agent_config)
            result = loop.run("Do something")

        assert result == "Done despite error."

        last_messages = (
            mock_client.chat.completions.create.call_args_list[-1].kwargs["messages"]
        )
        tool_results = [m for m in last_messages if m.get("role") == "tool"]
        assert any("ERROR" in m["content"] for m in tool_results)


# ---------------------------------------------------------------------------
# Test: max iterations exceeded → RuntimeError
# ---------------------------------------------------------------------------

class TestMaxIterations:
    def test_raises_after_max_iterations(self, agent_config: AppConfig):
        import json

        agent_config.agent.max_iterations = 3

        tool_call = _make_tool_call(
            call_id="call_inf",
            name="list_dir",
            arguments=json.dumps({"path": "."}),
        )
        always_tool_msg = _make_message(None, tool_calls=[tool_call])

        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.return_value = _make_response(
                always_tool_msg
            )

            loop = AgentLoop(agent_config)
            with pytest.raises(RuntimeError, match=r"max_iterations|within \d+ iterations"):
                loop.run("Loop forever")

        assert mock_client.chat.completions.create.call_count == 3


# ---------------------------------------------------------------------------
# Test: Memory standalone behaviour
# ---------------------------------------------------------------------------

class TestMemory:
    def test_initial_state(self):
        mem = Memory(system_prompt="You are a test agent.")
        assert mem.turn_count == 0
        messages = mem.all()
        assert messages[0]["role"] == "system"

    def test_add_and_count(self):
        mem = Memory(system_prompt="sys")
        mem.add({"role": "user", "content": "hi"})
        mem.add({"role": "assistant", "content": "hello"})
        assert mem.turn_count == 2

    def test_clear_keeps_system(self):
        mem = Memory(system_prompt="sys")
        mem.add({"role": "user", "content": "hi"})
        mem.clear(keep_system=True)
        assert mem.turn_count == 0
        assert mem.all()[0]["role"] == "system"

    def test_export_writes_json(self, tmp_path: Path):
        mem = Memory(
            system_prompt="sys",
            persist=True,
            export_path=str(tmp_path / "memory"),
        )
        mem.add({"role": "user", "content": "test"})
        out = mem.export(label="test_session")
        assert out.exists()
        import json
        data = json.loads(out.read_text(encoding="utf-8"))
        assert any(m["role"] == "user" for m in data)

    def test_maybe_export_skips_when_persist_false(self, tmp_path: Path):
        mem = Memory(
            system_prompt="sys",
            persist=False,
            export_path=str(tmp_path / "memory"),
        )
        result = mem.maybe_export()
        assert result is None
