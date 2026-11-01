import logging
from string import Template
from typing import Any
from agents.base_agent import BaseAgent

class TemplateCompletionAgent(BaseAgent):
    name = "TemplateCompletionAgent"
    capabilities = ("template",)

    def run(self, template: str, variables: dict) -> str:
        try:
            # safe_substitute ignores missing keys instead of raising.
            # If you want strict behavior, use .substitute().
            return Template(template).safe_substitute(**variables)
        except Exception as e:
            self.logger.error("template error: %s", e)
            return f"Error formatting template: {e}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "render":
            return self.run(args[0], args[1] if len(args) > 1 else {})
        return f"TemplateCompletionAgent - command '{command}' not implemented."