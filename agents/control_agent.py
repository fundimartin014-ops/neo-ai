from typing import Any
from agents.base_agent import BaseAgent
from agents.registry import AgentRegistry

class ControlAgent(BaseAgent):
    name = "ControlAgent"
    capabilities = ("coordinate", "health")

    def __init__(self, registry: AgentRegistry = None, **kw):
        super().__init__(**kw)
        self.registry = registry

    def run(self, input_data: str) -> str:
        self.logger.info("ControlAgent: %s", input_data)
        if input_data == "health" and self.registry:
            return str({n: a.health() for n, a in self.registry.all().items()})
        return f"ControlAgent received: {input_data}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "health":
            return self.run("health")
        if command == "list":
            return str(list(self.registry.all().keys())) if self.registry else "[]"
        return f"ControlAgent - command '{command}' not implemented."