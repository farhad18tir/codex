from __future__ import annotations

import asyncio
import time


class AsyncRateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        self._interval = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delta = now - self._last_call
            if delta < self._interval:
                await asyncio.sleep(self._interval - delta)
            self._last_call = time.monotonic()
