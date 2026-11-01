from typing import Any, Callable, List
from agents.base_agent import BaseAgent

class SecurityAgent(BaseAgent):
    name = "SecurityAgent"
    capabilities = ("security",)

    def __init__(self, rules: List[Callable[[str], bool]] = None, **kw):
        super().__init__(**kw)
        self.alerts: List[str] = []
        self.rules = rules or []

    def add_rule(self, rule: Callable[[str], bool]) -> None:
        self.rules.append(rule)

    def run(self, event: str) -> str:
        self.alerts.append(event)
        for rule in self.rules:
            try:
                if rule(event):
                    if self.bus:
                        self.bus.publish("security.alert", {"event": event})
                    return f"ALERT: rule matched for '{event}'"
            except Exception as e:
                self.logger.warning("rule failed: %s", e)
        return f"Recorded: {event}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "alerts":
            return "\n".join(self.alerts) if self.alerts else "(none)"
        return f"SecurityAgent - command '{command}' not implemented."