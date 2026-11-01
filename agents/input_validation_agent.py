import re
from typing import Any, Tuple
from agents.base_agent import BaseAgent

class InputValidationAgent(BaseAgent):
    name = "InputValidationAgent"
    capabilities = ("validate",)

    SQL_INJECTION = re.compile(r"(\b(select|insert|update|delete|drop|union)\b.*\b(from|into|where|table)\b)", re.I)
    XSS = re.compile(r"<\s*script|javascript:|onerror\s*=", re.I)

    def validate(self, text: str) -> Tuple[bool, str]:
        if not isinstance(text, str):
            return False, "not a string"
        if len(text) > 100_000:
            return False, "too long"
        if self.SQL_INJECTION.search(text):
            return False, "possible SQL injection"
        if self.XSS.search(text):
            return False, "possible XSS"
        return True, "ok"

    def sanitize(self, text: str) -> str:
        return re.sub(r"[<>]", "", text)

    def run(self, input_data: str) -> str:
        ok, reason = self.validate(input_data)
        return f"{'OK' if ok else 'REJECTED'}: {reason}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "check":
            return self.run(args[0])
        if command == "sanitize":
            return self.sanitize(args[0])
        return f"InputValidationAgent - command '{command}' not implemented."