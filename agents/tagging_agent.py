import json
from typing import Any, Dict, List
from agents.base_agent import BaseAgent

class TaggingAgent(BaseAgent):
    name = "TaggingAgent"
    capabilities = ("tag",)

    RULES = {
        "urgent": ["urgent", "asap", "immediately"],
        "bug":    ["bug", "error", "crash", "broken"],
        "feature":["feature", "request", "enhancement"],
        "question":["how", "what", "why", "?"],
    }

    def __init__(self, **kw):
        super().__init__(**kw)
        self.tagged: List[Dict[str, Any]] = []

    def _auto_tag(self, text: str) -> str:
        t = text.lower()
        for tag, keys in self.RULES.items():
            if any(k in t for k in keys):
                return tag
        return "general"

    def run(self, item: Dict[str, Any]) -> str:
        text = str(item.get("text", item))
        tag = item.get("tag") or self._auto_tag(text)
        self.tagged.append({"item": item, "tag": tag})
        return f"Tagged as {tag}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "list":
            return json.dumps(self.tagged, default=str)
        return f"TaggingAgent - command '{command}' not implemented."