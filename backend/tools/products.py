"""Vector store powered product retrieval tool (placeholder implementation)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.tools.base import Tool, ToolContext, ToolResponse


class ProductsTool(Tool):
    """Return drinkware recommendations using cached metadata."""

    name = "products"

    def __init__(self, index_path: Path, metadata_path: Path) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self._catalogue: list[dict[str, Any]] | None = None

    def _load_catalogue(self) -> list[dict[str, Any]]:
        if self._catalogue is not None:
            return self._catalogue

        if not self.metadata_path.exists():
            self._catalogue = []
            return self._catalogue

        with self.metadata_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, list):
                self._catalogue = data
            else:
                self._catalogue = []
        return self._catalogue

    async def run(self, context: ToolContext) -> ToolResponse:
        catalogue = self._load_catalogue()
        if not catalogue or not self.index_path.exists():
            return ToolResponse(
                content="Product catalogue is not ready yet. Please try again later.",
                data={"catalogue_loaded": bool(catalogue), "index_exists": self.index_path.exists()},
                success=False,
            )

        query = context.turn.content.lower()
        matches = self._search_catalogue(query, catalogue)

        if not matches:
            return ToolResponse(
                content="I couldn't find a matching drinkware item. Could you be more specific?",
                data={"results": []},
                success=False,
            )

        summary = "; ".join(f"{item['name']} ({item.get('size', 'N/A')})" for item in matches[:3])
        return ToolResponse(
            content=f"Top drinkware picks: {summary}.",
            data={"results": matches[:3]},
        )

    def _search_catalogue(self, query: str, catalogue: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tokens = {token.strip() for token in query.split() if len(token) > 2}
        results: list[dict[str, Any]] = []
        for item in catalogue:
            haystack = " ".join(
                str(item.get(key, "")).lower() for key in ("name", "description", "tags")
            )
            if any(token in haystack for token in tokens):
                results.append(item)
        return results
