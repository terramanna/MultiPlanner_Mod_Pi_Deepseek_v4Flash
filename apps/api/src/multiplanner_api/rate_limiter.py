"""Simple in-memory rate limiter.

No extra dependencies. Tracks requests per client IP using
a sliding-window counter. Default: 30 req/min.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import FastAPI, HTTPException, Request


class InMemoryRateLimiter:
    def __init__(self, requests_per_minute: int = 30) -> None:
        self._requests_per_minute = requests_per_minute
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request, call_next: Callable) -> ...:
        client = request.client.host if request.client else "unknown"
        now = time.time()
        window = self._windows[client]
        # prune entries older than 60 seconds
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.pop(0)
        if len(window) >= self._requests_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
        window.append(now)
        return await call_next(request)


def add_rate_limiter(app: FastAPI, requests_per_minute: int = 30) -> None:
    app.middleware("http")(InMemoryRateLimiter(requests_per_minute))