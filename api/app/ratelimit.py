"""Thread-safe, per-process fixed-window throttling for the portfolio demo."""

import math
from collections.abc import Callable
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int = 30, *, clock: Callable[[], float] = monotonic):
        if limit < 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be nonnegative")
        self.limit = limit
        self.clock = clock
        self._window: int | None = None
        self._counts: dict[str, int] = {}
        self._lock = Lock()

    def check(self, client_ip: str) -> None:
        if self.limit == 0:
            return
        # State is per-process only. For Lambda/multiple instances, use API Gateway
        # throttling or Redis instead; this cannot enforce a distributed quota.
        with self._lock:
            now = self.clock()
            window = math.floor(now / 60)
            if window != self._window:
                self._counts.clear()
                self._window = window
            count = self._counts.get(client_ip, 0)
            if count >= self.limit:
                raise HTTPException(
                    status_code=429, detail="Rate limit exceeded",
                    headers={"Retry-After": str(max(1, math.ceil((window + 1) * 60 - now)))},
                )
            self._counts[client_ip] = count + 1


def rate_limit(request: Request) -> None:
    # Use the ASGI peer address, never trust caller-supplied forwarding headers here.
    request.app.state.rate_limiter.check(request.client.host if request.client else "unknown")
