"""Simple in-memory rate limiter.

No extra dependencies. Tracks requests per client IP using
a sliding-window counter. Default: 30 req/min.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable, Iterable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Routes that legitimately see high-fanout or high-frequency traffic from a
# single client (health polling, per-file cache downloads, map tile bursts)
# and should not share the global per-IP bucket with everything else.
DEFAULT_EXEMPT_PATHS: tuple[str, ...] = ("/healthz",)
DEFAULT_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/v1/subsets/file",
    "/api/v1/tiles/",
)


class InMemoryRateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 30,
        exempt_paths: Iterable[str] = DEFAULT_EXEMPT_PATHS,
        exempt_prefixes: Iterable[str] = DEFAULT_EXEMPT_PREFIXES,
    ) -> None:
        self._requests_per_minute = requests_per_minute
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._exempt_paths = frozenset(exempt_paths)
        self._exempt_prefixes = tuple(exempt_prefixes)

    def _is_exempt(self, path: str) -> bool:
        if path in self._exempt_paths:
            return True
        return any(path.startswith(prefix) for prefix in self._exempt_prefixes)

    async def __call__(self, request: Request, call_next: Callable) -> ...:
        if self._is_exempt(request.url.path):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()
        window = self._windows[client]
        # prune entries older than 60 seconds
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.pop(0)
        if len(window) >= self._requests_per_minute:
            # Raising HTTPException here would escape Starlette's inner
            # ExceptionMiddleware (this runs as outer middleware), so it
            # would surface as a 500 instead of a 429. Return the response
            # directly instead.
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )
        window.append(now)
        return await call_next(request)


def add_rate_limiter(
    app: FastAPI,
    requests_per_minute: int = 30,
    exempt_paths: Iterable[str] = DEFAULT_EXEMPT_PATHS,
    exempt_prefixes: Iterable[str] = DEFAULT_EXEMPT_PREFIXES,
) -> None:
    app.middleware("http")(
        InMemoryRateLimiter(requests_per_minute, exempt_paths, exempt_prefixes)
    )