"""Exception handling utilities."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("zus.errors")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: D401
    """Return a generic JSON error response while logging the exception."""

    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Something unexpected happened. Please try again later.",
        },
    )
