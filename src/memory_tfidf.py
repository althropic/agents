"""
TF-IDF math helpers and the memory_search_tool formatter.

Separated from memory_store.py to keep both files under the 200-line limit.

Exports:
    _tokenize(text)              -> List[str]
    _tf(tokens)                  -> dict[str, float]
    _cosine(a, b)                -> float
    memory_search_tool(query, top_k, store) -> str
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING, List

from src.logger import get_logger

if TYPE_CHECKING:
    from src.memory_store import VectorMemory

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokenize(text: str) -> List[str]:
    """Lowercase and split text into alphanumeric/underscore tokens."""
    return _TOKEN_RE.findall(text.lower())


def _tf(tokens: List[str]) -> dict[str, float]:
    """Term frequency: count / total."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[t] * b[t] for t in shared)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def memory_search_tool(query: str, top_k: int, store: "VectorMemory") -> str:
    """Query *store* and format results as a string for the LLM."""
    logger.debug("memory_search_tool: query=%r top_k=%d", query, top_k)
    results = store.query(query, top_k=top_k)
    if not results:
        return "(no results — index may be empty; run /index to build it)"
    lines = []
    for doc_id, score, snippet in results:
        lines.append(f"[{score:.3f}] {doc_id}")
        if snippet:
            lines.append(f"    {snippet[:120]}")
    return "\n".join(lines)
