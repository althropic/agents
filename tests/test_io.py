"""
Unit tests for src/io.py — the write_output() stdout writer.

Guards the streaming regression: chunks must concatenate when called with
``end=""`` so streamed answers don't fragment across lines.
"""

from __future__ import annotations

from src.io import write_output


class TestWriteOutput:
    def test_default_appends_newline(self, capsys):
        write_output("hello")
        assert capsys.readouterr().out == "hello\n"

    def test_end_empty_writes_no_trailing_newline(self, capsys):
        write_output("chunk", end="")
        assert capsys.readouterr().out == "chunk"

    def test_custom_end(self, capsys):
        write_output("a", end="b")
        assert capsys.readouterr().out == "ab"

    def test_streaming_chunks_concatenate_then_one_newline(self, capsys):
        # Mirror the REPL streaming loop: chunks with end="", then a trailing
        # write_output("\n") — which emits "\n\n" (ends the answer's last line
        # plus the blank-line separator before the next prompt).
        for piece in ("Hel", "lo", " ", "world"):
            write_output(piece, end="")
        write_output("\n")
        assert capsys.readouterr().out == "Hello world\n\n"
