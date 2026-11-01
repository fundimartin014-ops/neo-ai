import re
from typing import Any
from agents.base_agent import BaseAgent

class SentimentAgent(BaseAgent):
    name = "SentimentAgent"
    capabilities = ("sentiment",)

    POSITIVE = {"good","great","excellent","love","happy","awesome","fantastic","nice","perfect","amazing"}
    NEGATIVE = {"bad","terrible","hate","awful","sad","angry","worst","horrible","broken","useless"}

    def run(self, text: str) -> str:
        words = re.findall(r"[a-zA-Z']+", text.lower())
        pos = sum(1 for w in words if w in self.POSITIVE)
        neg = sum(1 for w in words if w in self.NEGATIVE)
        if pos > neg: return "positive"
        if neg > pos: return "negative"
        return "neutral"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "analyze":
            return self.run(args[0] if args else "")
        return f"SentimentAgent - command '{command}' not implemented."