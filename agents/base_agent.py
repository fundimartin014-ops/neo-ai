"""Unified agent contract. Async-first, with a sync fallback bridge."""
from __future__ import annotations

import asyncio
import logging
from typing import Any


class BaseAgent:
    name: str = "BaseAgent"
    capabilities: tuple[str, ...] = ()

    def __init__(self, bus: Any = None, config: dict[str, Any] | None = None):
        self.bus = bus
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)

    # --- sync API (override for simple agents) ------------------------------
    def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def handle_command(self, command: str, *args: Any) -> Any:
        raise NotImplementedError

    # --- async API (defaults bridge to sync via thread pool) ----------------
    async def arun(self, *args: Any, **kwargs: Any) -> Any:
        from agents.telemetry import get_tracer
        tracer = get_tracer("agents")
        with tracer.start_as_current_span(f"agent.{self.name}.run") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("agent.method", "run")
            try:
                result = await asyncio.to_thread(self.run, *args, **kwargs)
                return result
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("error", str(exc))
                raise

    async def ahandle_command(self, command: str, *args: Any) -> Any:
        # Universal shortcut: {"command": "run", "args": [...]} -> arun(*args)
        if command == "run":
            return await self.arun(*args)
        return await asyncio.to_thread(self.handle_command, command, *args)

    # --- lifecycle ----------------------------------------------------------
    def health(self) -> dict[str, Any]:
        return {"name": self.name, "status": "ok", "capabilities": list(self.capabilities)}

    def shutdown(self) -> None:
        pass

    async def ashutdown(self) -> None:
        await asyncio.to_thread(self.shutdown)