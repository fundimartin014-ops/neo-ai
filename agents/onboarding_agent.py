from typing import Any, Set
from agents.base_agent import BaseAgent

class OnboardingAgent(BaseAgent):
    name = "OnboardingAgent"
    capabilities = ("onboard",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.onboarded_users: Set[str] = set()

    def run(self, user_id: str) -> str:
        if user_id in self.onboarded_users:
            return "Welcome back!"
        self.onboarded_users.add(user_id)
        return f"Hello, user {user_id}! Let's get started."

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "list":
            return str(sorted(self.onboarded_users))
        return f"OnboardingAgent - command '{command}' not implemented."