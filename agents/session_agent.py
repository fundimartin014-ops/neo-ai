from __future__ import annotations

import json
from typing import Any

from agents.base_agent import BaseAgent
from agents.persistence import SessionRepository


class SessionAgent(BaseAgent):
    name = "SessionAgent"
    capabilities = ("session",)

    def __init__(self, repo: SessionRepository, **kw: Any) -> None:
        super().__init__(**kw)
        self.repo = repo

    async def arun(self, session_id: str, data: dict | None = None) -> str:
        if data is not None:
            await self.repo.upsert(session_id, data)
            return f"Session {session_id} saved."
        return json.dumps(await self.repo.get(session_id) or {}, default=str)

    async def ahandle_command(self, command: str, *args: Any) -> str:
        if command == "show":
            return json.dumps(await self.repo.all(), default=str)
        if command == "drop":
            await self.repo.delete(args[0])
            return f"Session {args[0]} dropped."
        return f"SessionAgent - command '{command}' not implemented."