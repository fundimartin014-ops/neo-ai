"""Pick the right bus based on env: BUS_BACKEND=memory|redis."""
from __future__ import annotations

import os

from agents.message_bus import MessageBus


def make_bus():
    backend = os.getenv("BUS_BACKEND", "memory").lower()
    if backend == "redis":
        from agents.message_bus_redis import RedisMessageBus
        return RedisMessageBus(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    return MessageBus()