from __future__ import annotations

import json
from typing import Any

from agents.base_agent import BaseAgent
from agents.persistence import MetricsRepository
from agents.schemas import Metric
from agents.tracing import get_trace_id


class MetricsAgent(BaseAgent):
    name = "MetricsAgent"
    capabilities = ("metrics",)

    def __init__(self, repo: MetricsRepository, **kw: Any) -> None:
        super().__init__(**kw)
        self.repo = repo

    async def arun(self, name: str, value: float, tags: dict | None = None) -> str:
        await self.repo.add(Metric(name=name, value=float(value), tags=tags or {}, trace_id=get_trace_id()))
        return "Metric recorded."

    async def ahandle_command(self, command: str, *args: Any) -> str:
        if command == "summary":
            return json.dumps(await self.repo.summary(), default=str)
        return f"MetricsAgent - command '{command}' not implemented."