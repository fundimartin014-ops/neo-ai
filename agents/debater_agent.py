from agents.base_agent import BaseAgent

class DebaterAgent(BaseAgent):
    name = "DebaterAgent"
    capabilities = ("critique",)

    def challenge(self, answer: str) -> str:
        a = answer.lower()
        if len(answer) < 40:
            return "Answer lacks depth"
        if "maybe" in a or "perhaps" in a or "i think" in a:
            return "Answer sounds uncertain"
        return "Answer is strong"

    def run(self, answer: str) -> str:
        return self.challenge(answer)

    def handle_command(self, command: str, *args):
        if command == "challenge":
            return self.challenge(args[0] if args else "")
        return f"DebaterAgent - command '{command}' not implemented."
