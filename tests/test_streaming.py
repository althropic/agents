"""
Integration tests for streaming in the ReAct agent loop (src/agent/loop.py).

The OpenAI client is fully mocked — streaming responses are simulated with
SimpleNamespace chunk objects. No real LLM endpoint is required.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent.loop import AgentLoop
from src.agent.memory import Memory
from src.config import AppConfig


# ---------------------------------------------------------------------------
# Helpers to build fake streaming chunks
# ---------------------------------------------------------------------------

def _make_stream_chunk(content=None, tool_calls=None):
    """Create a fake streaming chunk matching OpenAI's delta format."""
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, finish_reason=None, index=0)
    return SimpleNamespace(choices=[choice])


def _make_tc_delta(index, call_id=None, name=None, arguments=None):
    """Create a fake tool call delta for a streaming chunk."""
    func = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=call_id, function=func)


# ---------------------------------------------------------------------------
# Fixture: AppConfig pointing at tmp_workspace
# ---------------------------------------------------------------------------

@pytest.fixture()
def agent_config(app_config: AppConfig, tmp_workspace: Path) -> AppConfig:
    """Return the test AppConfig with workspace and allowed_roots set to tmp_workspace."""
    app_config.workspace = tmp_workspace.resolve()
    app_config.file_access.allowed_roots = ["."]
    return app_config


# ---------------------------------------------------------------------------
# Test: streaming single-turn final answer
# ---------------------------------------------------------------------------

class TestStreamSingleTurn:
    def test_yields_text_chunks(self, agent_config: AppConfig):
        chunks = [
            _make_stream_chunk(content="Hello"),
            _make_stream_chunk(content=", "),
            _make_stream_chunk(content="world!"),
        ]
        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.return_value = iter(chunks)

            loop = AgentLoop(agent_config)
            result = list(loop.stream("Hi"))

        assert result == ["Hello", ", ", "world!"]

    def test_stream_with_memory_yields_chunks(self, agent_config: AppConfig):
        chunks = [
            _make_stream_chunk(content="The answer is "),
            _make_stream_chunk(content="42"),
        ]
        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.return_value = iter(chunks)

            loop = AgentLoop(agent_config)
            mem = Memory(system_prompt="test")
            result = list(loop.stream_with_memory("What is 6*7?", mem))

        assert result == ["The answer is ", "42"]
        # Final answer should be stored in memory
        messages = mem.all()
        assert messages[-1]["role"] == "assistant"
        assert messages[-1]["content"] == "The answer is 42"


# ---------------------------------------------------------------------------
# Test: streaming tool call then final answer
# ---------------------------------------------------------------------------

class TestStreamToolCallThenAnswer:
    def test_streams_after_tool(
        self, agent_config: AppConfig, tmp_workspace: Path
    ):
        hello_path = str(tmp_workspace / "hello.txt")

        tool_chunks = [
            _make_stream_chunk(tool_calls=[
                _make_tc_delta(0, call_id="call_1", name="read_file",
                               arguments=json.dumps({"path": hello_path}))
            ]),
        ]
        text_chunks = [
            _make_stream_chunk(content="The file says: "),
            _make_stream_chunk(content="Hello, world!"),
        ]

        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.side_effect = [
                iter(tool_chunks),
                iter(text_chunks),
            ]

            loop = AgentLoop(agent_config)
            result = list(loop.stream(f"Read {hello_path}"))

        assert result == ["The file says: ", "Hello, world!"]
        assert mock_client.chat.completions.create.call_count == 2

        # Verify the tool result was fed back into the second call
        last_call_messages = (
            mock_client.chat.completions.create.call_args_list[-1].kwargs["messages"]
        )
        tool_results = [m for m in last_call_messages if m.get("role") == "tool"]
        assert len(tool_results) == 1
        assert "Hello, world!" in tool_results[0]["content"]


# ---------------------------------------------------------------------------
# Test: streaming max iterations exceeded
# ---------------------------------------------------------------------------

class TestStreamMaxIterations:
    def test_raises_after_max_iterations(self, agent_config: AppConfig):
        agent_config.agent.max_iterations = 3

        def make_tool_stream(**kw):
            return iter([
                _make_stream_chunk(tool_calls=[
                    _make_tc_delta(0, call_id="call_inf", name="list_dir",
                                   arguments=json.dumps({"path": "."}))
                ]),
            ])

        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.side_effect = make_tool_stream

            loop = AgentLoop(agent_config)
            with pytest.raises(
                RuntimeError, match=r"max_iterations|within \d+ iterations"
            ):
                list(loop.stream("Loop forever"))

        assert mock_client.chat.completions.create.call_count == 3


# ---------------------------------------------------------------------------
# Test: empty content in stream is handled
# ---------------------------------------------------------------------------

class TestStreamEmptyContent:
    def test_no_chunks_when_content_is_none(self, agent_config: AppConfig):
        chunks = [_make_stream_chunk(content=None)]
        with patch("src.agent.loop.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.return_value = iter(chunks)

            loop = AgentLoop(agent_config)
            result = list(loop.stream("Say nothing"))

        assert result == []
