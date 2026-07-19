"""Observability & ingress hardening middleware.

Correlation ids flow into every log line and back out on the response header. The
security middleware rejects oversized bodies early and sets baseline security
headers. The error-tracking hook is optional and dependency-free.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.logging import correlation_id, get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = correlation_id.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            logger.info(
                "http_request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
            correlation_id.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, max_body_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_body_bytes = max_body_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > self._max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "payload_too_large",
                        "message": f"Request body exceeds {self._max_body_bytes} bytes",
                    }
                },
                headers=_SECURITY_HEADERS,
            )
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
