"""Synchronize ZUS outlet metadata into SQLite.

The script currently expects a local JSON file describing outlets. When
network access is permitted, replace the loader to fetch and parse the
official store listings.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync outlet metadata into SQLite database")
    parser.add_argument(
        "--input-file",
        type=Path,
        help="Path to local JSON file containing outlet records.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("../db/outlets.db"),
        help="Path to the SQLite database that stores outlet information.",
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing outlet table before inserting new records.",
    )
    return parser.parse_args()


def load_outlets(path: Path) -> list[dict]:
    if not path or not path.exists():
        raise FileNotFoundError("Provide --input-file pointing to a local outlets JSON export")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError("Expected top-level JSON array of outlet records")

    return data


def ensure_schema(conn: sqlite3.Connection, drop_existing: bool) -> None:
    if drop_existing:
        conn.execute("DROP TABLE IF EXISTS outlets")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS outlets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            state TEXT,
            postcode TEXT,
            latitude REAL,
            longitude REAL,
            opening_hours TEXT,
            services TEXT
        )
        """
    )


def upsert_outlets(conn: sqlite3.Connection, outlets: list[dict]) -> int:
    cursor = conn.cursor()
    inserted = 0
    for outlet in outlets:
        cursor.execute(
            """
            INSERT INTO outlets (name, address, city, state, postcode, latitude, longitude, opening_hours, services)
            VALUES (:name, :address, :city, :state, :postcode, :latitude, :longitude, :opening_hours, :services)
            """,
            {
                "name": outlet.get("name"),
                "address": outlet.get("address"),
                "city": outlet.get("city"),
                "state": outlet.get("state"),
                "postcode": outlet.get("postcode"),
                "latitude": outlet.get("latitude"),
                "longitude": outlet.get("longitude"),
                "opening_hours": outlet.get("opening_hours"),
                "services": ", ".join(outlet.get("services", [])),
            },
        )
        inserted += 1
    conn.commit()
    return inserted


def main() -> None:
    args = parse_args()
    outlets = load_outlets(args.input_file)

    args.database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.database)
    try:
        ensure_schema(conn, drop_existing=args.drop_existing)
        count = upsert_outlets(conn, outlets)
    finally:
        conn.close()

    print(f"Imported {count} outlets into {args.database}")


if __name__ == "__main__":
    main()
