from __future__ import annotations

import json
from typing import Any

from agents.base_agent import BaseAgent
from agents.persistence import AuditRepository
from agents.schemas import AuditEntry
from agents.tracing import get_trace_id, get_user_id


class AuditAgent(BaseAgent):
    name = "AuditAgent"
    capabilities = ("audit",)

    def __init__(self, repo: AuditRepository, **kw: Any) -> None:
        super().__init__(**kw)
        self.repo = repo

    async def arun(self, event: str, details: dict | None = None) -> str:
        entry = AuditEntry(
            event=event,
            details=details or {},
            trace_id=get_trace_id(),
            user_id=get_user_id() or None,
        )
        row_id = await self.repo.add(entry)
        self.logger.info("audit recorded", extra={"agent": self.name, "event": event})
        return f"Audit log entry added (id={row_id})."

    async def ahandle_command(self, command: str, *args: Any) -> str:
        if command == "recent":
            limit = int(args[0]) if args else 100
            return json.dumps(await self.repo.recent(limit=limit), default=str)
        if command == "by_event":
            return json.dumps(await self.repo.recent(event=args[0]), default=str)
        return f"AuditAgent - command '{command}' not implemented."