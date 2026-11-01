import json
from typing import Any, Dict
from agents.base_agent import BaseAgent

class UserProfileAgent(BaseAgent):
    name = "UserProfileAgent"
    capabilities = ("profile",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.profiles: Dict[str, Dict[str, Any]] = {}

    def run(self, user_id: str, profile_update: dict) -> str:
        self.profiles.setdefault(user_id, {}).update(profile_update)
        return "Profile updated."

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "show":
            return json.dumps(self.profiles.get(args[0], {}), default=str)
        if command == "all":
            return json.dumps(self.profiles, default=str)
        return f"UserProfileAgent - command '{command}' not implemented."