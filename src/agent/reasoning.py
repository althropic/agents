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
    """Return the reasoning text on a streaming *delta*, or None.

    The OpenAI SDK only deserialises known fields, so non-standard fields
    (e.g. Ollama's ``reasoning``) arrive in ``delta.model_extra``.  We
    check there first, then fall back to getattr for SDK versions that do
    expose these fields natively.
    """
    extra: dict = getattr(delta, "model_extra", None) or {}
    for field in _REASONING_FIELDS:
        val = extra.get(field) or getattr(delta, field, None)
        if val:
            return val
    return None
