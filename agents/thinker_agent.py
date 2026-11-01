from agents.base_agent import BaseAgent

class ThinkerAgent(BaseAgent):
    name = "ThinkerAgent"
    capabilities = ("reason",)

    def think(self, query: str) -> str:
        return f"Logical reasoning suggests: {query}"

    def run(self, query: str) -> str:
        return self.think(query)

    def handle_command(self, command: str, *args):
        if command == "think":
            return self.think(args[0] if args else "")
        return f"ThinkerAgent - command '{command}' not implemented."