"""
Conversation memory for the agent loop.

Stores the full OpenAI message list in-memory.
Optionally persists each session to a JSON file under export_path.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger import get_logger

logger = get_logger(__name__)

Message = Dict[str, Any]


class Memory:
    """In-memory conversation history with optional JSON export."""

    def __init__(
        self,
        system_prompt: str,
        persist: bool = False,
        export_path: Optional[str] = None,
    ) -> None:
        self._messages: List[Message] = [
            {"role": "system", "content": system_prompt}
        ]
        self._persist = persist
        self._export_path = Path(export_path) if export_path else Path(".agent_memory")
        logger.info(
            "Memory initialised: persist=%s export_path=%s",
            persist,
            self._export_path,
        )

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def add(self, message: Message) -> None:
        """Append a message dict to the history."""
        self._messages.append(message)
        logger.debug(
            "Memory.add: role=%s content_len=%s",
            message.get("role"),
            len(str(message.get("content", ""))),
        )

    def all(self) -> List[Message]:
        """Return the full message list (system prompt included)."""
        return list(self._messages)

    def clear(self, keep_system: bool = True) -> None:
        """Clear history, optionally preserving the system prompt."""
        system = self._messages[0] if keep_system else None
        self._messages = [system] if system else []
        logger.info("Memory cleared (keep_system=%s)", keep_system)

    @property
    def turn_count(self) -> int:
        """Number of non-system messages."""
        return len(self._messages) - 1

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def export(self, label: Optional[str] = None) -> Path:
        """
        Write the current history to a JSON file.
        Returns the path written to.
        """
        self._export_path.mkdir(parents=True, exist_ok=True)
        name = label or f"session_{int(time.time())}"
        out = self._export_path / f"{name}.json"
        out.write_text(
            json.dumps(self._messages, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Memory exported: %s (%d messages)", out, len(self._messages))
        return out

    def maybe_export(self, label: Optional[str] = None) -> Optional[Path]:
        """Export only if persist=True was configured."""
        if self._persist:
            return self.export(label)
        return None
