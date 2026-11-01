from tools.web import WebTool
from typing import Any, Dict

class ToolRouter:
    """
    Routes high-level plans to actual tool execution.
    """
    def __init__(self):
        self.web = WebTool()

    def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        if plan.get("tool") == "web":
            return self.web.search(plan.get("entities"))
        if plan.get("tool") == "memory_first":
            # To do: Add memory search
            return self.web.search(plan.get("entities"))
        return {"answer": "No valid plan."}