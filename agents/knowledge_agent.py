from typing import Any, Dict
from agents.base_agent import BaseAgent

class KnowledgeAgent(BaseAgent):
    name = "KnowledgeAgent"
    capabilities = ("answer",)

    def __init__(self, kb: Dict[str, str] = None, **kw):
        super().__init__(**kw)
        self.knowledge_base: Dict[str, str] = dict(kb or {})

    def teach(self, question: str, answer: str) -> None:
        self.knowledge_base[question.strip().lower()] = answer

    def run(self, question: str) -> str:
        key = question.strip().lower()
        if key in self.knowledge_base:
            return self.knowledge_base[key]
        # substring fallback
        for k, v in self.knowledge_base.items():
            if k in key or key in k:
                return v
        return f"No knowledge entry for: {question}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "teach":
            self.teach(args[0], args[1])
            return "Taught."
        if command == "ask":
            return self.run(args[0])
        return f"KnowledgeAgent - command '{command}' not implemented."