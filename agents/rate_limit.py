"""Token-bucket rate limiter, per-agent, in-memory with optional SQLite persistence."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class Bucket:
    capacity: int
    refill_per_sec: float
    tokens: float = field(init=False)
    last: float = field(init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last = time.monotonic()

    def try_take(self, n: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.last = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False

    @property
    def retry_after(self) -> float:
        if self.tokens >= 1:
            return 0.0
        return (1 - self.tokens) / self.refill_per_sec


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, Bucket] = {}
        self._lock = asyncio.Lock()

    def configure(self, agent: str, capacity: int, refill_per_sec: float) -> None:
        self._buckets[agent] = Bucket(capacity=capacity, refill_per_sec=refill_per_sec)

    async def acquire(self, agent: str, cost: int = 1) -> tuple[bool, float]:
        async with self._lock:
            b = self._buckets.get(agent)
            if b is None:
                return True, 0.0
            if b.try_take(cost):
                return True, 0.0
            return False, b.retry_after


# Module-level default limiter, configured at startup.
default_limiter = RateLimiter()