from typing import Any, List
from agents.base_agent import BaseAgent

class LoggingAgent(BaseAgent):
    name = "LoggingAgent"
    capabilities = ("log",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.logs: List[str] = []

    def run(self, log_message: str) -> str:
        self.logs.append(log_message)
        self.logger.info("captured event: %s", log_message)
        return f"LoggingAgent logged: {log_message}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "show_logs":
            return "\n".join(self.logs) if self.logs else "(no logs)"
        return f"LoggingAgent - command '{command}' not implemented."