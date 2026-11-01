from typing import Any
from agents.base_agent import BaseAgent

class SampleAgent(BaseAgent):
    name = "SampleAgent"
    capabilities = ("echo",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.state = {}

    def run(self, input_data: str) -> str:
        self.state["last"] = input_data
        return f"SampleAgent handled: {input_data}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "last":
            return self.state.get("last", "(none)")
        return f"SampleAgent - command '{command}' not implemented."