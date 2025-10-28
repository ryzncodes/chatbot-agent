"""Text2SQL-inspired outlet lookup tool (placeholder implementation)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.tools.base import Tool, ToolContext, ToolResponse


class OutletsTool(Tool):
    """Return outlet details using simple LIKE filtering."""

    name = "outlets"

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    async def run(self, context: ToolContext) -> ToolResponse:
        if not self.database_path.exists():
            return ToolResponse(
                content="Outlet database unavailable right now. Please try again later.",
                data={"database_exists": False},
                success=False,
            )

        query = context.turn.content.lower()
        rows = self._search_outlets(query)

        if not rows:
            return ToolResponse(
                content="I couldn't find an outlet matching that description.",
                data={"results": []},
                success=False,
            )

        formatted = [f"{row['name']} — opens {row['opening_hours'] or 'TBD'}" for row in rows[:3]]
        return ToolResponse(
            content="Here are the closest matches:\n" + "\n".join(formatted),
            data={"results": [dict(row) for row in rows[:3]]},
        )

    def _search_outlets(self, query: str):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        like_query = f"%{query.replace('%', '')}%"
        try:
            rows = conn.execute(
                """
                SELECT name, opening_hours, services, city, state
                FROM outlets
                WHERE LOWER(name) LIKE LOWER(?)
                   OR LOWER(city) LIKE LOWER(?)
                   OR LOWER(state) LIKE LOWER(?)
                ORDER BY name ASC
                LIMIT 5
                """,
                (like_query, like_query, like_query),
            ).fetchall()
        finally:
            conn.close()
        return rows
