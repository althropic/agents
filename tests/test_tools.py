"""
Unit tests for src/agent/tools.py.

All tests use tmp_workspace (conftest.py) so no real project files are touched.
allowed_roots is always scoped to the temp directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agent.tools import (
    build_tool_map,
    grep,
    list_dir,
    read_file,
    search_files,
    write_file,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roots(tmp: Path):
    return [tmp.resolve()]


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

class TestReadFile:
    def test_reads_existing_file(self, tmp_workspace: Path):
        result = read_file(str(tmp_workspace / "hello.txt"), _roots(tmp_workspace))
        assert result == "Hello, world!"

    def test_reads_nested_file(self, tmp_workspace: Path):
        result = read_file(
            str(tmp_workspace / "subdir" / "nested.txt"), _roots(tmp_workspace)
        )
        assert result == "Nested content."

    def test_rejects_path_outside_roots(self, tmp_workspace: Path, tmp_path: Path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        with pytest.raises(PermissionError):
            read_file(str(outside), _roots(tmp_workspace))

    def test_rejects_oversized_file(self, tmp_workspace: Path):
        big = tmp_workspace / "big.txt"
        big.write_text("x" * 1025, encoding="utf-8")  # > 1 KB
        with pytest.raises(ValueError, match="exceeds limit"):
            read_file(str(big), _roots(tmp_workspace), max_size_kb=1)

    def test_raises_for_missing_file(self, tmp_workspace: Path):
        with pytest.raises(FileNotFoundError):
            read_file(str(tmp_workspace / "nope.txt"), _roots(tmp_workspace))


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

class TestWriteFile:
    def test_creates_new_file(self, tmp_workspace: Path):
        target = tmp_workspace / "output.txt"
        result = write_file(str(target), "hello write", _roots(tmp_workspace))
        assert target.read_text(encoding="utf-8") == "hello write"
        assert "hello write" in result or str(len("hello write")) in result

    def test_overwrites_existing_file(self, tmp_workspace: Path):
        target = tmp_workspace / "hello.txt"
        write_file(str(target), "new content", _roots(tmp_workspace))
        assert target.read_text(encoding="utf-8") == "new content"

    def test_creates_parent_dirs(self, tmp_workspace: Path):
        target = tmp_workspace / "deep" / "dir" / "file.txt"
        write_file(str(target), "deep", _roots(tmp_workspace))
        assert target.exists()

    def test_rejects_path_outside_roots(self, tmp_workspace: Path, tmp_path: Path):
        outside = tmp_path.parent / "evil.txt"
        with pytest.raises(PermissionError):
            write_file(str(outside), "data", _roots(tmp_workspace))


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------

class TestListDir:
    def test_lists_root(self, tmp_workspace: Path):
        result = list_dir(str(tmp_workspace), _roots(tmp_workspace))
        assert "hello.txt" in result
        assert "subdir" in result

    def test_lists_subdir(self, tmp_workspace: Path):
        result = list_dir(
            str(tmp_workspace / "subdir"), _roots(tmp_workspace)
        )
        assert "nested.txt" in result

    def test_empty_dir(self, tmp_workspace: Path):
        empty = tmp_workspace / "empty"
        empty.mkdir()
        result = list_dir(str(empty), _roots(tmp_workspace))
        assert result == "(empty directory)"

    def test_raises_for_file(self, tmp_workspace: Path):
        with pytest.raises(NotADirectoryError):
            list_dir(str(tmp_workspace / "hello.txt"), _roots(tmp_workspace))

    def test_rejects_path_outside_roots(self, tmp_workspace: Path):
        import tempfile
        with tempfile.TemporaryDirectory() as outside:
            with pytest.raises(PermissionError):
                list_dir(outside, _roots(tmp_workspace))


# ---------------------------------------------------------------------------
# search_files
# ---------------------------------------------------------------------------

class TestSearchFiles:
    def test_finds_by_extension(self, tmp_workspace: Path):
        result = search_files(str(tmp_workspace), "*.txt", _roots(tmp_workspace))
        assert "hello.txt" in result

    def test_recursive_glob(self, tmp_workspace: Path):
        result = search_files(str(tmp_workspace), "**/*.txt", _roots(tmp_workspace))
        assert "nested.txt" in result

    def test_no_matches(self, tmp_workspace: Path):
        result = search_files(str(tmp_workspace), "*.py", _roots(tmp_workspace))
        assert result == "(no matches)"

    def test_raises_for_file_root(self, tmp_workspace: Path):
        with pytest.raises(NotADirectoryError):
            search_files(
                str(tmp_workspace / "hello.txt"), "*.txt", _roots(tmp_workspace)
            )


# ---------------------------------------------------------------------------
# grep
# ---------------------------------------------------------------------------

class TestGrep:
    def test_finds_matching_line(self, tmp_workspace: Path):
        result = grep(
            str(tmp_workspace / "hello.txt"), "world", _roots(tmp_workspace)
        )
        assert "1:" in result
        assert "Hello, world!" in result

    def test_no_matches(self, tmp_workspace: Path):
        result = grep(
            str(tmp_workspace / "hello.txt"), "zzznomatch", _roots(tmp_workspace)
        )
        assert result == "(no matches)"

    def test_regex_pattern(self, tmp_workspace: Path):
        target = tmp_workspace / "multi.txt"
        target.write_text("foo 1\nbar 2\nfoo 3", encoding="utf-8")
        result = grep(str(target), r"foo \d", _roots(tmp_workspace))
        assert "foo 1" in result
        assert "foo 3" in result
        assert "bar 2" not in result

    def test_rejects_oversized_file(self, tmp_workspace: Path):
        big = tmp_workspace / "big.txt"
        big.write_text("x" * 1025, encoding="utf-8")
        with pytest.raises(ValueError, match="exceeds limit"):
            grep(str(big), "x", _roots(tmp_workspace), max_size_kb=1)


# ---------------------------------------------------------------------------
# build_tool_map
# ---------------------------------------------------------------------------

class TestBuildToolMap:
    def test_all_keys_present(self, tmp_workspace: Path):
        tool_map = build_tool_map(_roots(tmp_workspace))
        assert set(tool_map.keys()) == {
            "read_file", "write_file", "list_dir", "search_files", "grep"
        }

    def test_read_file_via_map(self, tmp_workspace: Path):
        tool_map = build_tool_map(_roots(tmp_workspace))
        result = tool_map["read_file"](path=str(tmp_workspace / "hello.txt"))
        assert result == "Hello, world!"

    def test_list_dir_via_map(self, tmp_workspace: Path):
        tool_map = build_tool_map(_roots(tmp_workspace))
        result = tool_map["list_dir"](path=str(tmp_workspace))
        assert "hello.txt" in result
