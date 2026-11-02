"""
Tests for src/memory_store.py — VectorMemory TF-IDF index.

No real embeddings or ML dependencies are needed — the index uses only the
Python stdlib.  Tests cover: add, query, save/load, workspace indexing, the
memory_search_tool function, and the /index slash command.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.agent.memory import Memory
from src.config import AppConfig
from src.memory_store import VectorMemory, _cosine, _tf, _tokenize


# ---------------------------------------------------------------------------
# Unit tests: text helpers
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_lowercases(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_splits_on_non_alnum(self):
        assert _tokenize("foo.bar-baz/qux") == ["foo", "bar", "baz", "qux"]

    def test_preserves_underscores(self):
        assert "my_func" in _tokenize("def my_func():")

    def test_empty_string(self):
        assert _tokenize("") == []


class TestTf:
    def test_sums_to_one_for_single_token(self):
        assert _tf(["word"]) == {"word": 1.0}

    def test_uniform_tokens(self):
        assert abs(_tf(["a", "a", "a"])["a"] - 1.0) < 1e-9

    def test_two_different_tokens(self):
        result = _tf(["a", "b"])
        assert abs(result["a"] - 0.5) < 1e-9
        assert abs(result["b"] - 0.5) < 1e-9

    def test_empty_tokens(self):
        assert _tf([]) == {}


class TestCosine:
    def test_identical_vectors_score_one(self):
        v = {"a": 1.0, "b": 2.0}
        assert abs(_cosine(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors_score_zero(self):
        assert _cosine({"a": 1.0}, {"b": 1.0}) == 0.0

    def test_zero_vector_returns_zero(self):
        assert _cosine({}, {"a": 1.0}) == 0.0


# ---------------------------------------------------------------------------
# VectorMemory.add / query
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path: Path) -> VectorMemory:
    return VectorMemory(tmp_path / "index.json")


class TestVectorMemoryAdd:
    def test_doc_count_increments(self, store):
        store.add("a", "hello world")
        assert store.doc_count == 1

    def test_replacing_doc_keeps_count(self, store):
        store.add("a", "hello world")
        store.add("a", "goodbye world")
        assert store.doc_count == 1

    def test_snippet_stored(self, store):
        store.add("doc1", "some content here")
        assert "some content here" in store._snippets["doc1"]


class TestVectorMemoryQuery:
    def test_returns_empty_when_no_docs(self, store):
        assert store.query("anything") == []

    def test_relevant_doc_scores_higher(self, store):
        store.add("rate_limit.py", "rate limiting logic token bucket")
        store.add("config.py", "database connection pool settings host port")
        results = store.query("rate limiting")
        assert results[0][0] == "rate_limit.py"

    def test_returns_at_most_top_k(self, store):
        for i in range(10):
            store.add(f"doc{i}", f"python function number {i}")
        assert len(store.query("python function", top_k=3)) <= 3

    def test_result_tuple_structure(self, store):
        store.add("x", "hello world test")
        doc_id, score, snippet = store.query("hello")[0]
        assert doc_id == "x"
        assert 0.0 < score <= 1.0
        assert isinstance(snippet, str)

    def test_unrelated_query_returns_empty(self, store):
        store.add("code.py", "database connection pool")
        assert store.query("xyzzy frobulate quux") == []


# ---------------------------------------------------------------------------
# VectorMemory.save / load
# ---------------------------------------------------------------------------

class TestVectorMemorySaveLoad:
    def test_save_creates_file(self, store):
        store.add("a", "hello world")
        store.save()
        assert store._index_path.exists()

    def test_load_restores_docs(self, store):
        store.add("a", "hello world")
        store.add("b", "goodbye world")
        store.save()
        store2 = VectorMemory(store._index_path)
        assert store2.load() is True
        assert store2.doc_count == 2

    def test_load_returns_false_when_missing(self, tmp_path):
        assert VectorMemory(tmp_path / "nonexistent.json").load() is False

    def test_load_handles_corrupt_file(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{ not valid json !!!", encoding="utf-8")
        assert VectorMemory(p).load() is False

    def test_query_works_after_roundtrip(self, store):
        store.add("rate_limit.py", "rate limiting token bucket")
        store.save()
        store2 = VectorMemory(store._index_path)
        store2.load()
        assert store2.query("rate limiting")[0][0] == "rate_limit.py"


# ---------------------------------------------------------------------------
# VectorMemory.index_workspace
# ---------------------------------------------------------------------------

class TestIndexWorkspace:
    def test_indexes_text_files(self, store, tmp_workspace: Path):
        count = store.index_workspace([tmp_workspace], max_file_size_kb=100)
        assert count >= 2  # hello.txt + subdir/nested.txt

    def test_skips_oversized_files(self, store, tmp_path):
        (tmp_path / "big.txt").write_text("x" * 200_000, encoding="utf-8")
        assert store.index_workspace([tmp_path], max_file_size_kb=10) == 0

    def test_skips_non_text_extensions(self, store, tmp_path):
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        (tmp_path / "code.py").write_text("def foo(): pass", encoding="utf-8")
        assert store.index_workspace([tmp_path]) == 1

    def test_handles_missing_root_gracefully(self, store, tmp_path):
        assert store.index_workspace([tmp_path / "does_not_exist"]) == 0

    def test_indexes_nested_files(self, store, tmp_workspace: Path):
        store.index_workspace([tmp_workspace])
        assert any("nested" in k for k in store._vectors)


# ---------------------------------------------------------------------------
# memory_search_tool function
# ---------------------------------------------------------------------------

class TestMemorySearchTool:
    def test_returns_results_when_indexed(self, store):
        from src.memory_store import memory_search_tool
        store.add("hello.txt", "Hello, world!")
        assert "hello.txt" in memory_search_tool("hello", 5, store)

    def test_returns_hint_when_empty(self, store):
        from src.memory_store import memory_search_tool
        result = memory_search_tool("anything", 5, store)
        assert "index" in result.lower()

    def test_respects_top_k(self, store):
        from src.memory_store import memory_search_tool
        for i in range(10):
            store.add(f"file{i}.py", f"python code function number {i}")
        result = memory_search_tool("python function", 2, store)
        lines = [ln for ln in result.splitlines() if ln.startswith("[")]
        assert len(lines) <= 2


# ---------------------------------------------------------------------------
# /index slash command
# ---------------------------------------------------------------------------

class TestIndexCommand:
    @pytest.fixture()
    def cfg(self, app_config: AppConfig, tmp_workspace: Path) -> AppConfig:
        app_config.workspace = tmp_workspace.resolve()
        app_config.file_access.allowed_roots = ["."]
        app_config.vector_memory.enabled = True
        app_config.vector_memory.max_file_size_kb = 100
        return app_config

    @pytest.fixture()
    def mem(self, cfg: AppConfig) -> Memory:
        return Memory(
            system_prompt="t",
            persist=False,
            export_path=str(cfg.resolved_memory_export_path()),
        )

    def test_disabled_prints_message(self, app_config: AppConfig, tmp_workspace: Path):
        from src import repl_commands
        app_config.workspace = tmp_workspace.resolve()
        app_config.vector_memory.enabled = False
        captured = []
        with patch("src.io.sys") as mock_sys:
            mock_sys.stdout.write = lambda t: captured.append(t)
            result = repl_commands.handle("/index", app_config, Memory(
                system_prompt="t", persist=False, export_path=str(tmp_workspace)
            ))
        assert result is True
        assert any("disabled" in s.lower() for s in captured)

    def test_builds_index_and_saves(self, cfg: AppConfig, mem: Memory):
        from src import repl_commands
        captured = []
        with patch("src.io.sys") as mock_sys:
            mock_sys.stdout.write = lambda t: captured.append(t)
            result = repl_commands.handle("/index", cfg, mem)
        assert result is True
        assert cfg.resolved_index_path().exists()
        assert "Index built" in "".join(captured)

    def test_attaches_store_to_cfg(self, cfg: AppConfig, mem: Memory):
        from src import repl_commands
        with patch("src.io.sys"):
            repl_commands.handle("/index", cfg, mem)
        assert cfg._vector_memory is not None  # noqa: SLF001

    def test_help_lists_index(self, cfg: AppConfig, mem: Memory):
        from src import repl_commands
        captured = []
        with patch("src.io.sys") as mock_sys:
            mock_sys.stdout.write = lambda t: captured.append(t)
            repl_commands.handle("/help", cfg, mem)
        assert "/index" in "".join(captured)
