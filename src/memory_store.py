"""
Persistent vector memory backed by a TF-IDF cosine-similarity index.

No external ML dependencies required — everything runs on the Python stdlib.
The index maps document IDs (file paths or session-turn labels) to their
TF-IDF term vectors.  Queries are vectorised the same way and ranked by
cosine similarity.

Design:
    - Documents are arbitrary (path, text) pairs.
    - The vocabulary is built incrementally; calling save() persists it.
    - load() restores a previous session's index so memory survives restarts.
    - index_workspace() walks the allowed roots, reads every text file under
      max_file_size_kb, and adds it to the index.

Usage:
    store = VectorMemory(index_path=Path(".agent_memory/index.json"))
    store.load()                        # no-op if file does not exist
    store.index_workspace(roots, max_kb)
    results = store.query("rate limiting", top_k=5)
    store.save()
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

from src.logger import get_logger
from src.memory_tfidf import _cosine, _tf, _tokenize  # noqa: F401 — re-exported
from src.memory_tfidf import memory_search_tool  # noqa: F401 — re-exported

logger = get_logger(__name__)


class VectorMemory:
    """TF-IDF document index with optional disk persistence."""

    def __init__(self, index_path: Path) -> None:
        self._index_path = index_path
        # doc_id → {term: tf_weight}  (IDF applied at query time)
        self._vectors: dict[str, dict[str, float]] = {}
        # doc_id → first 200 chars of source text (for result snippets)
        self._snippets: dict[str, str] = {}
        # term → document frequency (how many docs contain the term)
        self._df: Counter = Counter()
        logger.info("VectorMemory init: index_path=%s", index_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def doc_count(self) -> int:
        return len(self._vectors)

    def add(self, doc_id: str, text: str) -> None:
        """Add or replace a document in the index."""
        tokens = _tokenize(text)
        tf = _tf(tokens)

        old_terms = set(self._vectors.get(doc_id, {}))
        new_terms = set(tf)
        for t in old_terms - new_terms:
            self._df[t] = max(0, self._df[t] - 1)
        for t in new_terms - old_terms:
            self._df[t] += 1

        self._vectors[doc_id] = tf
        self._snippets[doc_id] = text[:200].replace("\n", " ")
        logger.debug("VectorMemory.add: doc_id=%s tokens=%d", doc_id, len(tokens))

    def query(self, text: str, top_k: int = 5) -> List[Tuple[str, float, str]]:
        """Return the *top_k* most similar documents as (doc_id, score, snippet).

        IDF weighting is applied at query time so late-added documents are
        scored correctly without a full index rebuild.
        """
        if not self._vectors:
            logger.debug("VectorMemory.query: index is empty")
            return []

        n = len(self._vectors)
        q_vec = self._apply_idf(_tf(_tokenize(text)), n)

        scored: list[tuple[str, float, str]] = []
        for doc_id, tf in self._vectors.items():
            score = _cosine(q_vec, self._apply_idf(tf, n))
            if score > 0:
                scored.append((doc_id, score, self._snippets.get(doc_id, "")))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = scored[:top_k]
        logger.debug(
            "VectorMemory.query: %r → %d results (top=%.3f)",
            text[:60], len(results), results[0][1] if results else 0.0,
        )
        return results

    def index_workspace(
        self,
        roots: List[Path],
        max_file_size_kb: int = 100,
        extensions: Optional[List[str]] = None,
    ) -> int:
        """Walk *roots* and index every readable text file."""
        if extensions is None:
            extensions = [".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".json"]
        ext_set = {e.lower() for e in extensions}
        added = 0
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() not in ext_set or not path.is_file():
                    continue
                if path.stat().st_size / 1024 > max_file_size_kb:
                    logger.debug("VectorMemory: skipping %s (too large)", path)
                    continue
                try:
                    self.add(str(path), path.read_text(encoding="utf-8", errors="ignore"))
                    added += 1
                except OSError as exc:
                    logger.warning("VectorMemory: could not read %s: %s", path, exc)
        logger.info(
            "VectorMemory.index_workspace: indexed %d files across %d roots",
            added, len(roots),
        )
        return added

    def save(self) -> None:
        """Persist the index to disk as JSON."""
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "vectors": self._vectors,
            "snippets": self._snippets,
            "df": dict(self._df),
        }
        self._index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "VectorMemory.save: wrote %d docs to %s",
            len(self._vectors), self._index_path,
        )

    def load(self) -> bool:
        """Load the index from disk. Returns True if the file was found."""
        if not self._index_path.exists():
            logger.info("VectorMemory.load: no index at %s", self._index_path)
            return False
        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._vectors = payload.get("vectors", {})
            self._snippets = payload.get("snippets", {})
            self._df = Counter(payload.get("df", {}))
            logger.info(
                "VectorMemory.load: loaded %d docs from %s",
                len(self._vectors), self._index_path,
            )
            return True
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("VectorMemory.load: corrupt index (%s) — starting fresh", exc)
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_idf(self, tf: dict[str, float], n: int) -> dict[str, float]:
        """Multiply TF values by smoothed IDF weights."""
        result = {}
        for term, freq in tf.items():
            df = self._df.get(term, 0)
            if df == 0:
                continue
            idf = math.log((n + 1) / (df + 1)) + 1
            result[term] = freq * idf
        return result
