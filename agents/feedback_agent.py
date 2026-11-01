import json
from typing import Any, Dict, List
from agents.base_agent import BaseAgent

class FeedbackAgent(BaseAgent):
    name = "FeedbackAgent"
    capabilities = ("feedback",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.feedback_entries: List[Dict[str, Any]] = []

    def run(self, entry: str) -> str:
        self.feedback_entries.append({"entry": entry})
        return "Thank you for your feedback!"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "list":
            return json.dumps(self.feedback_entries, default=str)
        return f"FeedbackAgent - command '{command}' not implemented."