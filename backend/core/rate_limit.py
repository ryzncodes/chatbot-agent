"""Simple in-memory rate limiter middleware.

This module implements a per-identity sliding-window rate limiter with a
per-minute window and a small per-second burst. Identity preference is
"user ID if available, else client IP".

Notes:
- This is in-memory per-process. In multi-worker deployments, limits are
  enforced per worker. For distributed limits, swap to a shared backend
  (e.g., Redis) in the future.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from .config import get_settings


@dataclass
class _Bucket:
    per_minute: deque[float]
    per_second: deque[float]


class InMemoryRateLimiter:
    def __init__(self, per_minute: int, per_second: int) -> None:
        self.per_minute_limit = per_minute
        self.per_second_limit = per_second
        self._buckets: dict[str, _Bucket] = {}

    def _get_bucket(self, key: str) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(per_minute=deque(), per_second=deque())
            self._buckets[key] = bucket
        return bucket

    def check(self, key: str) -> tuple[bool, int, int, int]:
        """Return whether allowed and (limit, remaining, reset_epoch_seconds).

        If not allowed, remaining will be 0 and second value is retry-after seconds.
        """

        now = time.monotonic()
        wall = int(time.time())
        bucket = self._get_bucket(key)

        # prune old timestamps
        one_minute = 60.0
        one_second = 1.0
        while bucket.per_minute and now - bucket.per_minute[0] >= one_minute:
            bucket.per_minute.popleft()
        while bucket.per_second and now - bucket.per_second[0] >= one_second:
            bucket.per_second.popleft()

        # compute remaining and reset
        remaining_min = self.per_minute_limit - len(bucket.per_minute)
        remaining_sec = self.per_second_limit - len(bucket.per_second)

        # Determine reset times for headers (approximate to wall clock)
        reset_min_sec = int(one_minute - (now - bucket.per_minute[0])) if bucket.per_minute else 0
        reset_sec_sec = int(one_second - (now - bucket.per_second[0])) if bucket.per_second else 0

        if remaining_min <= 0 or remaining_sec <= 0:
            # Deny and calculate retry-after as the max of the two windows
            retry_after = max(reset_min_sec, reset_sec_sec)
            limit = min(self.per_minute_limit, self.per_second_limit)
            return False, limit, 0, wall + retry_after

        # record this request
        bucket.per_minute.append(now)
        bucket.per_second.append(now)

        remaining = min(remaining_min, remaining_sec) - 1
        limit = min(self.per_minute_limit, self.per_second_limit)
        reset_epoch = wall + max(reset_min_sec, reset_sec_sec)
        return True, limit, max(remaining, 0), reset_epoch


def _extract_client_ip(request: Request) -> str:
    """Return the client IP for rate limiting purposes.

    Security note: Trusting the `X-Forwarded-For` header is only safe when the app
    is deployed behind a trusted reverse proxy or load balancer that strips or
    overwrites this header. Otherwise, a malicious client could spoof their IP and
    bypass limits. This function consults the `trust_x_forwarded_for` setting; when
    false (the default, safe for direct deployments), the header is ignored and the
    connection's peer address is used instead.
    """

    settings = get_settings()

    if settings.trust_x_forwarded_for:
        # Use X-Forwarded-For if present (first IP), else request.client.host
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # take the first non-empty trimmed value
            ip = xff.split(",")[0].strip()
            if ip:
                return ip

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _extract_identity(request: Request) -> tuple[str, bool]:
    """Return (key, is_authenticated) for rate limiting.

    Prefers an explicit user ID header when present; otherwise falls back
    to the client IP. This keeps implementation simple without a full auth layer.
    """

    user_id = request.headers.get("x-user-id")
    if user_id:
        return f"user:{user_id}", True
    ip = _extract_client_ip(request)
    return f"ip:{ip}", False


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return await call_next(request)

    # Path matching helpers (suffix wildcard '/*')
    def _matches(patterns: list[str], value: str) -> bool:
        for pattern in patterns:
            if pattern.endswith("/*"):
                prefix = pattern[:-1]
                if value.startswith(prefix):
                    return True
            elif value == pattern:
                return True
        return False

    path = request.url.path

    # If include list is non-empty, only enforce for those paths
    if settings.rate_limit_include_paths:
        if not _matches(settings.rate_limit_include_paths, path):
            return await call_next(request)

    # Exempt paths regardless (e.g., health, metrics, tools)
    if _matches(settings.rate_limit_exempt_paths, path):
        return await call_next(request)

    key, is_auth = _extract_identity(request)
    if is_auth:
        limiter = request.app.state.__dict__.setdefault(  # type: ignore[attr-defined]
            "_rate_limiter_auth",
            InMemoryRateLimiter(
                per_minute=settings.rate_limit_auth_per_minute,
                per_second=settings.rate_limit_burst_per_second,
            ),
        )
    else:
        limiter = request.app.state.__dict__.setdefault(  # type: ignore[attr-defined]
            "_rate_limiter_unauth",
            InMemoryRateLimiter(
                per_minute=settings.rate_limit_unauth_per_minute,
                per_second=settings.rate_limit_burst_per_second,
            ),
        )

    allowed, limit, remaining, reset_epoch = limiter.check(key)
    if not allowed:
        retry_after = max(1, int(reset_epoch - time.time()))
        return JSONResponse(
            status_code=429,
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_epoch),
            },
            content={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please retry later.",
                "retry_after_seconds": retry_after,
            },
        )

    response = await call_next(request)
    # Attach headers for successful responses too
    response.headers.setdefault("X-RateLimit-Limit", str(limit))
    response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
    response.headers.setdefault("X-RateLimit-Reset", str(reset_epoch))
    return response
