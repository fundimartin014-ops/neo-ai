import json
from typing import Any, Dict, List
from agents.base_agent import BaseAgent

class DataCollectionAgent(BaseAgent):
    name = "DataCollectionAgent"
    capabilities = ("collect",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.data: List[Dict[str, Any]] = []

    def run(self, data_point: Dict[str, Any]) -> str:
        self.data.append(data_point)
        return f"Data collected ({len(self.data)} total)."

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "show":
            return json.dumps(self.data, default=str)
        if command == "clear":
            self.data.clear()
            return "Cleared."
        return f"DataCollectionAgent - command '{command}' not implemented."