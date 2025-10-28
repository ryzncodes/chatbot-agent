"""Lightweight in-memory metrics collector."""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass
from typing import Dict


@dataclass
class MetricSnapshot:
    total_requests: int
    tool_calls: Dict[str, int]
    planner_intents: Dict[str, int]


class MetricsCollector:
    """Thread-safe counter storage for basic service metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_requests = 0
        self._tool_calls: Counter[str] = Counter()
        self._intents: Counter[str] = Counter()

    def record_request(self, intent: str, action: str) -> None:
        with self._lock:
            self._total_requests += 1
            self._intents[intent] += 1
            self._tool_calls[action] += 1

    def snapshot(self) -> MetricSnapshot:
        with self._lock:
            return MetricSnapshot(
                total_requests=self._total_requests,
                tool_calls=dict(self._tool_calls),
                planner_intents=dict(self._intents),
            )
