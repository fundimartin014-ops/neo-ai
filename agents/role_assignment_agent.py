import json
from typing import Any, Dict, Set
from agents.base_agent import BaseAgent

class RoleAssignmentAgent(BaseAgent):
    name = "RoleAssignmentAgent"
    capabilities = ("roles",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.roles: Dict[str, Set[str]] = {}

    def run(self, user_id: str, role: str) -> str:
        self.roles.setdefault(user_id, set()).add(role)
        return f"Role '{role}' assigned to {user_id}."

    def has_role(self, user_id: str, role: str) -> bool:
        return role in self.roles.get(user_id, set())

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "list":
            return json.dumps({u: sorted(r) for u, r in self.roles.items()})
        if command == "check":
            return str(self.has_role(args[0], args[1]))
        return f"RoleAssignmentAgent - command '{command}' not implemented."