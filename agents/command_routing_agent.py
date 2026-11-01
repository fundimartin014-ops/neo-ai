from typing import Any, Callable, Dict

from agents.base_agent import BaseAgent
from agents.registry import AgentRegistry


class CommandRoutingAgent(BaseAgent):
    name = "CommandRoutingAgent"
    capabilities = ("route", "dispatch")

    def __init__(self, registry: AgentRegistry = None, **kw):
        super().__init__(**kw)
        self.registry = registry
        self.routes: Dict[str, Callable[..., Any]] = {}

    def add_route(self, command: str, handler: Callable[..., Any]) -> None:
        self.routes[command] = handler

    def add_agent_route(self, command: str, agent_name: str, sub_command: str = None):
        def _dispatch(*args):
            return self.registry.command(agent_name, sub_command or command, *args)
        self.add_route(command, _dispatch)

    def run(self, command: str, *args: Any) -> str:
        handler = self.routes.get(command)
        return handler(*args) if handler else f"Unknown command: {command}"

    def handle_command(self, command: str, *args: Any) -> str:
        return self.run(command, *args)