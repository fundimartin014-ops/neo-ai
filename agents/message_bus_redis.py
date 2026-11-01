"""Redis pub/sub + lists for cross-process agents. Drop-in for MessageBus."""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Callable, Optional

from agents.schemas import MessageType
from agents.tracing import get_trace_id

try:
    import redis
    import redis.asyncio as aioredis
except ImportError as exc:
    raise ImportError("pip install redis to use RedisMessageBus") from exc


class RedisMessageBus:
    """Cross-process bus. Uses:
      - RPUSH/BLPOP on 'queue:<name>' for inboxes
      - PUBLISH/SUBSCRIBE on 'events' channel for pub/sub
    """

    def __init__(self, url: str = "redis://localhost:6379/0", prefix: str = "agents") -> None:
        self.url = url
        self.prefix = prefix
        self._sync = redis.Redis.from_url(url, decode_responses=True)
        self._sub_thread: threading.Thread | None = None
        self._sub_stop = threading.Event()
        self._handlers: dict[str, list[Callable]] = {}
        self._stopped = threading.Event()

    # --- inboxes ----------------------------------------------------------
    def _q(self, name: str) -> str:
        return f"{self.prefix}:queue:{name}"

    def send(self, target: str, message: dict | Any) -> None:
        if self._stopped.is_set():
            return
        if hasattr(message, "model_dump"):
            message = message.model_dump()
        message.setdefault("trace_id", get_trace_id())
        self._sync.rpush(self._q(target), json.dumps(message, default=str))

    def receive(self, name: str, timeout: Optional[float] = None) -> Optional[dict]:
        t = int(timeout) if timeout else 1
        item = self._sync.blpop(self._q(name), timeout=t)
        if not item:
            return None
        _, payload = item
        return json.loads(payload)

    # --- pub/sub ----------------------------------------------------------
    def subscribe(self, event: str, handler: Callable) -> None:
        self._handlers.setdefault(event, []).append(handler)
        self._ensure_sub_thread()

    def unsubscribe(self, event: str, handler: Callable) -> None:
        self._handlers[event] = [h for h in self._handlers.get(event, []) if h is not handler]

    def publish(self, event: str, payload: Any = None) -> None:
        body = {"event": event, "payload": payload, "trace_id": get_trace_id()}
        self._sync.publish(f"{self.prefix}:events", json.dumps(body, default=str))

    def _ensure_sub_thread(self) -> None:
        if self._sub_thread and self._sub_thread.is_alive():
            return

        def loop():
            pubsub = self._sync.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(f"{self.prefix}:events")
            while not self._sub_stop.is_set():
                try:
                    msg = pubsub.get_message(timeout=1.0)
                except Exception:
                    continue
                if not msg:
                    continue
                try:
                    body = json.loads(msg["data"])
                except Exception:
                    continue
                for h in list(self._handlers.get(body.get("event"), [])):
                    try:
                        h(body.get("payload"))
                    except Exception as exc:
                        print(f"[redis-bus] handler failed: {exc}")

        self._sub_thread = threading.Thread(target=loop, daemon=True, name="RedisBusSub")
        self._sub_thread.start()

    # --- lifecycle --------------------------------------------------------
    def stop(self) -> None:
        self._stopped.set()
        self._sub_stop.set()
        for name in ("executor", "critic", "memory"):
            self._sync.rpush(self._q(name), json.dumps({"type": MessageType.SHUTDOWN.value}))
        if self._sub_thread:
            self._sub_thread.join(timeout=2)

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()