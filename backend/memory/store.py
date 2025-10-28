"""Memory store abstractions and SQLite implementation skeleton."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import sqlite3

from .models import ConversationSnapshot, MessageTurn, SlotState


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

    @abstractmethod
    def upsert_slots(self, conversation_id: str, slots: SlotState) -> None:
        """Persist slot state for a conversation."""


class SQLiteMemoryStore(MemoryStore):
    """SQLite-backed memory store. Persistence logic to be implemented."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        """Create required tables if they do not exist."""

        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS slots (
                    conversation_id TEXT PRIMARY KEY,
                    topic TEXT,
                    operation TEXT,
                    location TEXT,
                    time_range TEXT,
                    product_type TEXT,
                    loyalty_status TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
                    ON messages (conversation_id, created_at DESC);
                """
            )

    def append_turn(self, turn: MessageTurn) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations(conversation_id) VALUES (?)",
                (turn.conversation_id,),
            )
            conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, created_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    turn.conversation_id,
                    turn.role,
                    turn.content,
                    turn.created_at.isoformat(),
                    json_dumps(turn.metadata),
                ),
            )

    def fetch_recent_turns(self, conversation_id: str, limit: int = 10) -> Sequence[MessageTurn]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT conversation_id, role, content, created_at, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()

        turns = [
            MessageTurn(
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                created_at=datetime_from_iso(row["created_at"]),
                metadata=json_loads(row["metadata"] or "{}"),
            )
            for row in rows
        ]
        turns.reverse()
        return turns

    def load_snapshot(self, conversation_id: str) -> ConversationSnapshot:
        turns = self.fetch_recent_turns(conversation_id, limit=100)

        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM slots WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()

        slots: SlotState = SlotState()
        if row:
            slots.update({k: row[k] for k in row.keys() if row[k] is not None and k != "conversation_id"})

        return ConversationSnapshot(conversation_id=conversation_id, turns=list(turns), slots=slots)

    def reset(self, conversation_id: str) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM slots WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))

    def iter_conversations(self) -> Iterable[str]:
        with self._connection() as conn:
            rows = conn.execute("SELECT conversation_id FROM conversations ORDER BY conversation_id")
            return [row["conversation_id"] for row in rows]

    def upsert_slots(self, conversation_id: str, slots: SlotState) -> None:
        """Persist slot state for a conversation."""

        with self._connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations(conversation_id) VALUES (?)",
                (conversation_id,),
            )
            data: dict[str, Any] = {"conversation_id": conversation_id}
            data.update({k: v for k, v in slots.items() if v is not None})
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" for _ in data)
            update_clause = ", ".join(
                f"{col}=excluded.{col}" for col in data if col != "conversation_id"
            )
            conn.execute(
                f"""
                INSERT INTO slots ({columns}) VALUES ({placeholders})
                ON CONFLICT(conversation_id) DO UPDATE SET {update_clause}
                """,
                tuple(data.values()),
            )


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, separators=(",", ":"))


def json_loads(value: str) -> dict[str, Any]:
    import json

    return json.loads(value)


def datetime_from_iso(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)
