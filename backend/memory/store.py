"""Memory store abstractions and SQLite implementation skeleton."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Sequence

from .models import ConversationSnapshot, MessageTurn


class MemoryStore(ABC):
    """Abstract interface for reading and writing conversation memory."""

    @abstractmethod
    def append_turn(self, turn: MessageTurn) -> None:
        """Persist a single conversational turn."""

    @abstractmethod
    def fetch_recent_turns(self, conversation_id: str, limit: int = 10) -> Sequence[MessageTurn]:
        """Return the most recent turns for a conversation."""

    @abstractmethod
    def load_snapshot(self, conversation_id: str) -> ConversationSnapshot:
        """Return a snapshot containing turns and tracked slot state."""

    @abstractmethod
    def reset(self, conversation_id: str) -> None:
        """Clear stored turns and slot state for a conversation."""

    @abstractmethod
    def iter_conversations(self) -> Iterable[str]:
        """Iterate over known conversation identifiers."""


class SQLiteMemoryStore(MemoryStore):
    """SQLite-backed memory store. Persistence logic to be implemented."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create required tables if they do not exist."""

        # TODO: Implement schema creation (messages table, slots table, indexes, etc.).
        pass

    def append_turn(self, turn: MessageTurn) -> None:
        # TODO: Persist turn to SQLite database.
        raise NotImplementedError

    def fetch_recent_turns(self, conversation_id: str, limit: int = 10) -> Sequence[MessageTurn]:
        # TODO: Fetch recent turns from SQLite.
        raise NotImplementedError

    def load_snapshot(self, conversation_id: str) -> ConversationSnapshot:
        # TODO: Build snapshot with turns and slots.
        raise NotImplementedError

    def reset(self, conversation_id: str) -> None:
        # TODO: Delete stored data for a conversation.
        raise NotImplementedError

    def iter_conversations(self) -> Iterable[str]:
        # TODO: Return iterator over conversation IDs.
        raise NotImplementedError
