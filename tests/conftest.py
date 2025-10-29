from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def conversation_calc_payload(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "conversation_calc.json").read_text(encoding="utf-8"))


@pytest.fixture
def products_query(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "products_query.json").read_text(encoding="utf-8"))
