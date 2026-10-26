"""
Stdout writer for user-facing output.

All modules in src/ must route terminal output through write_output()
rather than calling print() directly.  This keeps print() out of src/
while preserving the separation between structured logs (logs/agent.log)
and interactive output (stdout).
"""

from __future__ import annotations

import sys


def write_output(text: str, end: str = "\n") -> None:
    """Write *text* to stdout, followed by *end* (a newline by default).

    Streaming callers pass ``end=""`` so chunks concatenate into flowing
    text instead of each landing on its own line.
    """
    sys.stdout.write(text + end)
    sys.stdout.flush()
