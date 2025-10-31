"""Vector store powered product retrieval tool using TF-IDF FAISS index."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import faiss  # type: ignore
import httpx
import numpy as np

from backend.tools.base import Tool, ToolContext, ToolResponse


class ProductsTool(Tool):
    """Return drinkware recommendations using cached metadata and FAISS index."""

    name = "products"
    _summarise_semaphore = asyncio.Semaphore(2)

    def __init__(
        self,
        index_path: Path,
        metadata_path: Path,
        *,
        openrouter_api_key: str | None = None,
        openrouter_model: str = "minimax/minimax-m2:free",
        openrouter_referer: str | None = None,
        openrouter_title: str | None = None,
        openrouter_rate_limit_per_sec: float = 1.0,
    ) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self._catalogue: list[dict[str, Any]] | None = None
        self._vocabulary: list[str] | None = None
        self._idf: np.ndarray | None = None
        self._index: faiss.Index | None = None
        self._openrouter_api_key = openrouter_api_key
        self._openrouter_model = openrouter_model
        self._openrouter_referer = openrouter_referer
        self._openrouter_title = openrouter_title or "ZUS AI Assistant"
        self._openrouter_min_interval = max(0.1, openrouter_rate_limit_per_sec)
        self._last_openrouter_call = 0.0
        self._rate_lock = asyncio.Lock()
        self._logger = logging.getLogger("zus.products")

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

        if (
            not isinstance(products, list)
            or not isinstance(vocabulary, list)
            or not isinstance(idf, list)
        ):
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
                content=(
                    "I couldn't understand that request. Could you rephrase the product "
                    "you're looking for?"
                ),
                data={"results": []},
                success=False,
            )

        faiss.normalize_L2(query_vector)
        scores, indices = index.search(query_vector, k=min(5, len(catalogue)))
        matches: list[dict[str, Any]] = []
        for idx, score in zip(indices[0], scores[0], strict=True):
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

        summary = await self._summarise_matches(matches)
        return ToolResponse(
            content=summary,
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

    async def _summarise_matches(self, matches: list[dict[str, Any]]) -> str:
        fallback = "; ".join(
            f"{item.get('name', 'Unknown')} ({item.get('size', 'N/A')})" for item in matches[:3]
        )
        fallback_text = f"Top drinkware picks: {fallback}."

        if not self._openrouter_api_key or not matches:
            return fallback_text

        snippet_lines = []
        for idx, item in enumerate(matches[:3]):
            name = item.get("name", "Unknown")
            size = item.get("size") or item.get("volume") or "N/A"
            price = item.get("price") or item.get("price_text") or ""
            description = item.get("description", "")
            tags = item.get("tags", [])
            line = f"{idx + 1}. {name} — size: {size}"
            if price:
                line += f", price: {price}"
            if tags:
                line += f", tags: {', '.join(tags)}"
            if description:
                line += f"\n   Notes: {description[:180]}"
            snippet_lines.append(line)

        prompt = "\n".join(snippet_lines)

        async with self._summarise_semaphore:
            async with self._rate_lock:
                now = time.monotonic()
                wait_for = self._openrouter_min_interval - (now - self._last_openrouter_call)
                if wait_for > 0:
                    await asyncio.sleep(wait_for)
                self._last_openrouter_call = time.monotonic()

            headers = {
                "Authorization": f"Bearer {self._openrouter_api_key}",
                "Content-Type": "application/json",
            }
            if self._openrouter_referer:
                headers["HTTP-Referer"] = self._openrouter_referer
            if self._openrouter_title:
                headers["X-Title"] = self._openrouter_title

            payload = {
                "model": self._openrouter_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a friendly ZUS Coffee assistant "
                            "summarising drinkware recommendations succinctly."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Produce exactly one warm sentence (maximum 25 words) "
                            "recommending up to two items from the list below. "
                            "Mention a standout size or feature, and end with a "
                            "gentle call to action.\n\nProducts:\n" + prompt
                        ),
                    },
                ],
            }

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = (
                        data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    )
                    if not content:
                        return fallback_text

                    content = " ".join(content.replace("\n", " ").split())

                    # Keep only the first sentence to avoid multi-sentence rambles.
                    if "." in content:
                        first_sentence = content.split(".")[0].strip()
                        if first_sentence:
                            content = first_sentence + "."

                    words = content.split()
                    if len(words) > 25:
                        content = " ".join(words[:25]).rstrip(",;") + "..."

                    return content
            except Exception as exc:  # noqa: BLE001
                self._logger.exception(
                    "OpenRouter summary failed",
                    extra={"error": str(exc)},
                )
                return fallback_text


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())
