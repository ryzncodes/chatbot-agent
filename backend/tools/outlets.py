"""Text2SQL-inspired outlet lookup tool with simple query interpretation."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

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

        interpretation = self._interpret_query(context.turn.content)
        rows, sql = self._search_outlets(interpretation)

        if not rows:
            return ToolResponse(
                content="I couldn't find an outlet matching that description.",
                data={"results": [], "sql": sql},
                success=False,
            )

        formatted = [f"{row['name']} — opens {row['opening_hours'] or 'TBD'}" for row in rows[:3]]
        return ToolResponse(
            content="Here are the closest matches:\n" + "\n".join(formatted),
            data={"results": [dict(row) for row in rows[:3]], "sql": sql},
        )

    def _interpret_query(self, query: str) -> Dict[str, Any]:
        lowered = query.lower()
        tokens = lowered.split()

        location: Optional[str] = None
        for token in tokens:
            token = token.strip(",.!?")
            if token in LOCATION_KEYWORDS:
                location = LOCATION_KEYWORDS[token]
                break
        if location is None:
            for keyword in LOCATION_KEYWORDS.values():
                if keyword.lower() in lowered:
                    location = keyword
                    break

        needs_hours = any(word in lowered for word in ("open", "close", "hour", "time"))
        needs_services = any(word in lowered for word in ("delivery", "pickup", "drive", "service"))

        service_filters: List[str] = []
        for service_keyword, service_value in SERVICE_KEYWORDS.items():
            if service_keyword in lowered:
                service_filters.append(service_value)

        return {
            "location": location,
            "needs_hours": needs_hours,
            "needs_services": needs_services,
            "service_filters": service_filters,
            "raw": lowered,
        }

    def _search_outlets(self, interpretation: Dict[str, Any]):
        base_fields = ["name", "city", "state"]
        if interpretation["needs_hours"]:
            base_fields.append("opening_hours")
        if interpretation["needs_services"]:
            base_fields.append("services")

        select_clause = ", ".join(dict.fromkeys(base_fields))
        sql = f"SELECT {select_clause} FROM outlets"
        where_clauses: List[str] = []
        params: List[Any] = []

        location = interpretation.get("location")
        if location:
            where_clauses.append(
                "("
                "LOWER(city) LIKE LOWER(?) OR "
                "LOWER(state) LIKE LOWER(?) OR "
                "LOWER(name) LIKE LOWER(?)"
                ")"
            )
            like_value = f"%{location}%"
            params.extend([like_value, like_value, like_value])

        services = interpretation.get("service_filters", [])
        for service in services:
            where_clauses.append("LOWER(services) LIKE LOWER(?)")
            params.append(f"%{service}%")

        if not where_clauses and interpretation.get("raw"):
            where_clauses.append("LOWER(name) LIKE LOWER(?)")
            params.append(f"%{interpretation['raw']}%")

        if where_clauses:
            sql = f"{sql} WHERE {' AND '.join(where_clauses)}"

        sql += " ORDER BY name ASC LIMIT 5"

        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return rows, sql


LOCATION_KEYWORDS = {
    "ss2": "SS 2",
    "pj": "Petaling Jaya",
    "petaling": "Petaling Jaya",
    "damansara": "Damansara",
    "kl": "Kuala Lumpur",
    "kuala": "Kuala Lumpur",
    "selangor": "Selangor",
}

SERVICE_KEYWORDS = {
    "delivery": "delivery",
    "pickup": "pickup",
    "drive": "drive",
    "drive-thru": "drive",
    "dine-in": "dine-in",
}
