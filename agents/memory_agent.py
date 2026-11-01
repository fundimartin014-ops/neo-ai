from __future__ import annotations

import threading
from typing import Any

from agents.base_agent import BaseAgent
from agents.message_bus import SHUTDOWN
from agents.persistence import MemoryRepository
from agents.schemas import MemoryItem
from agents.tracing import get_trace_id


class MemoryAgent(BaseAgent):
    name = "MemoryAgent"
    capabilities = ("store", "recall")

    def __init__(self, repo: MemoryRepository, **kw: Any) -> None:
        super().__init__(**kw)
        self.repo = repo
        self._thread: threading.Thread | None = None

    async def arun(self, results: list[tuple[str, Any]]) -> str:
        for step, result in results:
            await self.repo.store(MemoryItem(key=str(step), value=result, tags={"trace": get_trace_id()}))
        return f"Stored {len(results)} items."

    async def ahandle_command(self, command: str, *args: Any) -> str:
        import json

        if command == "recall":
            hits = await self.repo.search(args[0], limit=int(args[1]) if len(args) > 1 else 10)
            return json.dumps(hits, default=str)
        if command == "all":
            return json.dumps(await self.repo.all(), default=str)
        return f"MemoryAgent - command '{command}' not implemented."

    # background consumer for bus-driven flow
    def start(self) -> None:
        def loop() -> None:
            import asyncio

            while not self.bus.stopped:
                msg = self.bus.receive("memory", timeout=0.5)
                if msg is None:
                    continue
                if msg.get("type") == SHUTDOWN:
                    break
                if msg.get("type") == "store":
                    asyncio.run(self.arun(msg["data"]))

        self._thread = threading.Thread(target=loop, daemon=True, name="MemoryAgent")
        self._thread.start()

    def shutdown(self) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)