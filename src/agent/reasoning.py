"""
Reasoning-trace extraction for OpenAI-compatible streaming.

Thinking models (e.g. Ollama's nemotron) emit their chain-of-thought in a
delta field whose name varies by server: Ollama's /v1 layer uses
``reasoning``, some servers use ``reasoning_content``, and the native
Ollama API uses ``thinking``. extract_reasoning() returns whichever is
present so callers can surface (or discard) the trace uniformly.
"""

from __future__ import annotations

# Order matters: check the common OpenAI-compatible field first.
_REASONING_FIELDS = ("reasoning", "reasoning_content", "thinking")


def extract_reasoning(delta) -> str | None:
    """Return the reasoning text on a streaming *delta*, or None."""
    for field in _REASONING_FIELDS:
        val = getattr(delta, field, None)
        if val:
            return val
    return None
