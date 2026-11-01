from typing import Any, Callable, Dict
from agents.base_agent import BaseAgent

class StatusAgent(BaseAgent):
    name = "StatusAgent"
    capabilities = ("status",)

    def __init__(self, checks: Dict[str, Callable[[], Any]] = None, **kw):
        super().__init__(**kw)
        self.checks = checks or {}
        self.last_status = "Initialized"

    def run(self, query: str = "") -> str:
        if query == "detailed" and self.checks:
            results = {}
            for name, fn in self.checks.items():
                try:
                    results[name] = fn()
                except Exception as e:
                    results[name] = f"error: {e}"
            return str(results)
        return f"Current status: {self.last_status}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "set":
            self.last_status = args[0]
            return "Status updated."
        return f"StatusAgent - command '{command}' not implemented."