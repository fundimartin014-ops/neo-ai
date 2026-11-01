from __future__ import annotations

from typing import Any, Optional

from agents.base_agent import BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def all(self) -> dict[str, BaseAgent]:
        return dict(self._agents)

    # --- async-first calls --------------------------------------------------
    async def arun(self, name: str, *args: Any, **kwargs: Any) -> Any:
        agent = self.get(name)
        if not agent:
            return f"Agent '{name}' not found."
        return await agent.arun(*args, **kwargs)

    async def acommand(self, name: str, command: str, *args: Any) -> Any:
        agent = self.get(name)
        if not agent:
            return f"Agent '{name}' not found."
        return await agent.ahandle_command(command, *args)

    # --- sync fallbacks -----------------------------------------------------
    def run(self, name: str, *args: Any, **kwargs: Any) -> Any:
        import asyncio

        return asyncio.run(self.arun(name, *args, **kwargs))

    def command(self, name: str, command: str, *args: Any) -> Any:
        import asyncio

        return asyncio.run(self.acommand(name, command, *args))

    def shutdown(self) -> None:
        for agent in self._agents.values():
            try:
                agent.shutdown()
            except Exception as exc:
                print(f"[registry] shutdown of {agent.name} failed: {exc}")