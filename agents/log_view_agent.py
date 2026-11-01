from typing import Any, List
from agents.base_agent import BaseAgent

class LogViewAgent(BaseAgent):
    name = "LogViewAgent"
    capabilities = ("logs",)

    def __init__(self, logs: List[str] = None, **kw):
        super().__init__(**kw)
        self.logs: List[str] = logs if logs is not None else []

    def run(self, filter_term: str = "", limit: int = 10) -> str:
        if not filter_term:
            result = self.logs[-limit:]
        else:
            result = [line for line in self.logs if filter_term in line][-limit:]
        return "\n".join(result) if result else "(no logs)"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "show":
            return self.run()
        if command == "filter":
            return self.run(args[0] if args else "")
        return f"LogViewAgent - command '{command}' not implemented."