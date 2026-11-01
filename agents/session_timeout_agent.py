import time
import json
from typing import Any, Dict
from agents.base_agent import BaseAgent
from agents.config import Config

class SessionTimeoutAgent(BaseAgent):
    name = "SessionTimeoutAgent"
    capabilities = ("session_timeout",)

    def __init__(self, timeout: float = None, **kw):
        super().__init__(**kw)
        self.timeout = timeout if timeout is not None else Config.SESSION_TIMEOUT
        self.sessions: Dict[str, float] = {}

    def run(self, session_id: str, activity: str = None) -> str:
        now = time.time()
        if activity:
            self.sessions[session_id] = now
            return "Session activity tracked."
        last = self.sessions.get(session_id)
        if last is None:
            return "Unknown session."
        if now - last > self.timeout:
            del self.sessions[session_id]
            return "Session expired."
        return "Session active."

    def sweep(self) -> int:
        now = time.time()
        expired = [s for s, t in self.sessions.items() if now - t > self.timeout]
        for s in expired:
            del self.sessions[s]
        return len(expired)

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "list":
            return json.dumps(self.sessions)
        if command == "sweep":
            return f"Expired {self.sweep()} session(s)."
        return f"SessionTimeoutAgent - command '{command}' not implemented."