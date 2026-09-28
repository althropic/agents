"""
Stdout writer for user-facing output.

All modules in src/ must route terminal output through write_output()
rather than calling print() directly.  This keeps print() out of src/
while preserving the separation between structured logs (logs/agent.log)
and interactive output (stdout).
"""

from __future__ import annotations

import sys


def write_output(text: str) -> None:
    """Write *text* followed by a newline to stdout."""
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
