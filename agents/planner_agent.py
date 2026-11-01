from __future__ import annotations

import json
from typing import Any

from agents.base_agent import BaseAgent
from agents.llm import PLANNER_SYSTEM, PLANNER_USER, get_llm


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    capabilities = ("plan",)

    def __init__(self, llm=None, fallback_to_heuristic: bool = True, **kw: Any) -> None:
        super().__init__(**kw)
        self.llm = llm or get_llm()
        self.fallback_to_heuristic = fallback_to_heuristic

    async def plan(self, goal: str) -> list[str]:
        try:
            data = await self.llm.chat_json(
                [
                    {"role": "system", "content": PLANNER_SYSTEM},
                    {"role": "user", "content": PLANNER_USER.format(goal=goal)},
                ],
                temperature=0.2,
            )
            steps = data.get("steps") or []
            if steps:
                return [str(s).strip() for s in steps if str(s).strip()]
        except Exception as exc:
            self.logger.warning("LLM plan failed, falling back: %s", exc)
        if self.fallback_to_heuristic:
            return self._heuristic(goal)
        return [goal]

    @staticmethod
    def _heuristic(goal: str) -> list[str]:
        import re
        parts = re.split(r"\s*(?:,|->|then|and then)\s*", goal.strip(), flags=re.I)
        return [p.strip() for p in parts if p.strip()] or [goal]

    async def arun(self, goal: str) -> str:
        plan = await self.plan(goal)
        if self.bus:
            self.bus.send("executor", {"type": "plan", "goal": goal, "data": plan})
        self.logger.info("planned %d steps", len(plan), extra={"agent": self.name, "goal": goal})
        return json.dumps({"goal": goal, "steps": plan})

    async def ahandle_command(self, command: str, *args: Any) -> str:
        if command == "plan":
            return json.dumps({"steps": await self.plan(args[0] if args else "")})
        return f"PlannerAgent - command '{command}' not implemented."