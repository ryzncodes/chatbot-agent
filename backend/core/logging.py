"""Logging utilities for the backend."""

from __future__ import annotations

import logging
import uuid
from typing import Callable

from fastapi import Request

logger = logging.getLogger("zus.request")


async def request_id_middleware(request: Request, call_next: Callable):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id

    logger.info("%s %s [rid=%s]", request.method, request.url.path, request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
