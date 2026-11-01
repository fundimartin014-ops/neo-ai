import json
from typing import Any, Dict, List
from agents.base_agent import BaseAgent

class IntegrationAgent(BaseAgent):
    name = "IntegrationAgent"
    capabilities = ("integrate",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.integrations: List[Dict[str, Any]] = []

    def run(self, service_info: Dict[str, Any]) -> str:
        self.integrations.append(service_info)
        return f"Integration with {service_info.get('name', 'unknown')} registered."

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "list":
            return json.dumps(self.integrations, default=str)
        return f"IntegrationAgent - command '{command}' not implemented."