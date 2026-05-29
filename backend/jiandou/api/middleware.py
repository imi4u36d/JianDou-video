"""API 中间件 — CORS、请求日志、限流。"""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的耗时和状态码。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        response = await call_next(request)
        elapsed = (time.time() - start) * 1000
        # Log to stderr (will go to uvicorn logs)
        print(
            f"[API] {request.method} {request.url.path} "
            f"→ {response.status_code} ({elapsed:.1f}ms)"
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的滑动窗口限流。

    默认: 60 requests / minute per IP
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        # Skip rate limiting for WebSocket upgrade
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        self._clients[client_ip] = [
            ts for ts in self._clients[client_ip] if ts > window_start
        ]

        if len(self._clients[client_ip]) >= self.max_requests:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "code": 429},
            )

        self._clients[client_ip].append(now)
        return await call_next(request)


def setup_cors(app, origins: list[str] | None = None):
    """添加 CORS 中间件。"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def setup_middleware(app, origins: list[str] | None = None):
    """安装所有中间件到 FastAPI 应用。"""
    # CORS first (outermost)
    setup_cors(app, origins)

    # Rate limiting
    app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)

    # Request logging (innermost)
    app.add_middleware(RequestLoggingMiddleware)
