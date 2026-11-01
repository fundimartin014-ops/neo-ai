"""Thread-safe named-inbox bus with pub/sub and graceful shutdown."""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Optional

from agents.schemas import Message, MessageType
from agents.tracing import get_trace_id

SHUTDOWN = MessageType.SHUTDOWN.value


class MessageBus:
    def __init__(self) -> None:
        self._inboxes: dict[str, queue.Queue] = {}
        self._handlers: dict[str, list[Callable]] = {}
        self._lock = threading.RLock()
        self._stopped = threading.Event()

    # --- inboxes ------------------------------------------------------------
    def register(self, name: str) -> queue.Queue:
        with self._lock:
            return self._inboxes.setdefault(name, queue.Queue())

    def send(self, target: str, message: dict | Message) -> None:
        if self._stopped.is_set():
            return
        if isinstance(message, Message):
            message = message.model_dump()
        message.setdefault("trace_id", get_trace_id())
        self.register(target).put(message)

    def receive(self, name: str, timeout: Optional[float] = None) -> Optional[dict]:
        try:
            return self.register(name).get(timeout=timeout)
        except queue.Empty:
            return None

    # --- pub/sub ------------------------------------------------------------
    def subscribe(self, event: str, handler: Callable) -> None:
        with self._lock:
            self._handlers.setdefault(event, []).append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        with self._lock:
            self._handlers[event] = [h for h in self._handlers.get(event, []) if h is not handler]

    def publish(self, event: str, payload: Any = None) -> None:
        for handler in list(self._handlers.get(event, [])):
            try:
                handler(payload)
            except Exception as exc:  # never let a subscriber kill the bus
                print(f"[bus] handler for '{event}' failed: {exc}")

    # --- lifecycle ----------------------------------------------------------
    def stop(self) -> None:
        self._stopped.set()
        with self._lock:
            for q in self._inboxes.values():
                q.put({"type": MessageType.SHUTDOWN.value})

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()