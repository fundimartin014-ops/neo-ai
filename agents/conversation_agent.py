import threading
from typing import Any, List, Dict
from agents.base_agent import BaseAgent

class ConversationAgent(BaseAgent):
    name = "ConversationAgent"
    capabilities = ("converse",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def run(self, input_data: str) -> str:
        with self._lock:
            self.history.append({"role": "user", "text": input_data})
        reply = f"ConversationAgent handled: {input_data}"
        with self._lock:
            self.history.append({"role": "assistant", "text": reply})
        return reply

    def handle_command(self, command: str, args: Any = None) -> str:
        if command == "history":
            return "\n".join(f"{m['role']}: {m['text']}" for m in self.history) or "(empty)"
        if command == "clear":
            self.history.clear()
            return "History cleared."
        return f"ConversationAgent - command '{command}' not implemented."