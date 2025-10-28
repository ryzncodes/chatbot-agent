"""Database utility helpers."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def sqlite_connection(path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with row factory enabled."""

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:  # noqa: BLE001
        conn.rollback()
        raise
    finally:
        conn.close()
