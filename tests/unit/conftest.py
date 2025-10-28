"""Pytest unit test fixtures."""

import pytest

from backend.memory.store import SQLiteMemoryStore


@pytest.fixture()
def memory_store(tmp_path):
    db_path = tmp_path / "memory.db"
    return SQLiteMemoryStore(db_path)
