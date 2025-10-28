"""Vector store powered product retrieval tool using TF-IDF FAISS index."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import faiss  # type: ignore
import numpy as np

from backend.tools.base import Tool, ToolContext, ToolResponse


class ProductsTool(Tool):
    """Return drinkware recommendations using cached metadata and FAISS index."""

    name = "products"

    def __init__(self, index_path: Path, metadata_path: Path) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self._catalogue: list[dict[str, Any]] | None = None
        self._vocabulary: list[str] | None = None
        self._idf: np.ndarray | None = None
        self._index: faiss.Index | None = None

    def _load_catalogue(self) -> list[dict[str, Any]]:
        if self._catalogue is not None and self._vocabulary is not None and self._idf is not None:
            return self._catalogue

        if not self.metadata_path.exists():
            self._catalogue = []
            self._vocabulary = []
            self._idf = np.array([], dtype=np.float32)
            return self._catalogue

        with self.metadata_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        products = data.get("products")
        vocabulary = data.get("vocabulary")
        idf = data.get("idf")

        if not isinstance(products, list) or not isinstance(vocabulary, list) or not isinstance(idf, list):
            self._catalogue = []
            self._vocabulary = []
            self._idf = np.array([], dtype=np.float32)
            return self._catalogue

        self._catalogue = products
        self._vocabulary = [str(token) for token in vocabulary]
        self._idf = np.array(idf, dtype=np.float32)
        return self._catalogue

    def _ensure_index(self) -> faiss.Index | None:
        if self._index is not None:
            return self._index
        if not self.index_path.exists():
            return None
        self._index = faiss.read_index(str(self.index_path))
        return self._index

    async def run(self, context: ToolContext) -> ToolResponse:
        catalogue = self._load_catalogue()
        index = self._ensure_index()
        if not catalogue or index is None or self._vocabulary is None or self._idf is None:
            return ToolResponse(
                content="Product catalogue is not ready yet. Please try again later.",
                data={
                    "catalogue_loaded": bool(catalogue),
                    "index_exists": self.index_path.exists(),
                },
                success=False,
            )

        query_vector = self._vectorize_query(context.turn.content)
        if query_vector is None:
            return ToolResponse(
                content="I couldn't understand that request. Could you rephrase the product you're looking for?",
                data={"results": []},
                success=False,
            )

        faiss.normalize_L2(query_vector)
        scores, indices = index.search(query_vector, k=min(5, len(catalogue)))
        matches: list[dict[str, Any]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < 0 or idx >= len(catalogue) or score <= 0:
                continue
            item = catalogue[idx]
            matches.append({"score": float(score), **item})

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

    def _vectorize_query(self, text: str) -> np.ndarray | None:
        if not text.strip() or self._vocabulary is None or self._idf is None:
            return None

        tokens = _tokenize(text)
        if not tokens:
            return None

        vocab_index = {token: idx for idx, token in enumerate(self._vocabulary)}
        vector = np.zeros((1, len(self._vocabulary)), dtype=np.float32)
        counts = Counter(tokens)
        for token, count in counts.items():
            idx = vocab_index.get(token)
            if idx is None:
                continue
            tf = count / len(tokens)
            vector[0, idx] = tf * self._idf[idx]
        if not vector.any():
            return None
        return vector


import re


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())
