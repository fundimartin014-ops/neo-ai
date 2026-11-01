import json
import uuid
from typing import Any, Dict
from agents.base_agent import BaseAgent

class TaskAgent(BaseAgent):
    name = "TaskAgent"
    capabilities = ("task",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.state: Dict[str, Dict[str, Any]] = {}

    def create(self, description: str) -> str:
        tid = uuid.uuid4().hex[:8]
        self.state[tid] = {"description": description, "status": "open"}
        return tid

    def complete(self, tid: str) -> str:
        if tid not in self.state:
            return f"No such task: {tid}"
        self.state[tid]["status"] = "done"
        return f"Task {tid} completed."

    def run(self, input_data: str) -> str:
        tid = self.create(input_data)
        return f"TaskAgent created task {tid}: {input_data}"

    def handle_command(self, command: str, *args) -> str:
        if command == "create":
            return self.create(args[0])
        if command == "complete":
            return self.complete(args[0])
        if command == "list":
            return json.dumps(self.state, default=str)
        return f"TaskAgent - command '{command}' not implemented."