import subprocess
import shlex
from typing import Any, List
from agents.base_agent import BaseAgent

class SystemAgent(BaseAgent):
    name = "SystemAgent"
    capabilities = ("shell",)

    # Strict allowlist of executables that can be invoked.
    ALLOWED = {"echo", "date", "whoami", "pwd", "ls", "cat", "wc"}

    def __init__(self, extra_allowed: List[str] = None, **kw):
        super().__init__(**kw)
        if extra_allowed:
            self.ALLOWED = self.ALLOWED | set(extra_allowed)

    def run(self, command_line: str) -> str:
        try:
            parts = shlex.split(command_line)
        except ValueError as e:
            return f"[system error] bad command: {e}"
        if not parts:
            return "[system error] empty command"
        prog = parts[0]
        if prog not in self.ALLOWED:
            return f"[system blocked] '{prog}' not in allowlist {sorted(self.ALLOWED)}"
        try:
            result = subprocess.run(
                parts, capture_output=True, text=True, timeout=10, check=False
            )
            out = (result.stdout or "") + (result.stderr or "")
            return out.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "[system error] timeout"
        except Exception as e:
            return f"[system error] {e}"

    def handle_command(self, command: str, *args: Any) -> str:
        return self.run(command)