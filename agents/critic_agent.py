import threading
from typing import Any, List, Tuple
from agents.base_agent import BaseAgent
from agents.message_bus import SHUTDOWN

class CriticAgent(BaseAgent):
    name = "CriticAgent"
    capabilities = ("evaluate",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self._thread = None

    def evaluate(self, results: List[Tuple[str, Any]]) -> bool:
        if not results:
            return False
        for _, result in results:
            if not result or len(str(result)) < 5:
                return False
        return True

    def run(self, results: list, goal: str = "") -> str:
        success = self.evaluate(results)
        if self.bus:
            if success:
                self.bus.send("memory", {"type": "store", "data": results})
                self.bus.publish("goal.completed", {"goal": goal, "results": results})
                self.logger.info("goal completed: %s", goal)
                return f"Goal completed: {goal}"
            else:
                self.bus.send("planner", {"type": "goal", "data": goal})
                self.bus.publish("goal.failed", {"goal": goal})
                self.logger.info("failure detected → replanning: %s", goal)
                return f"Failure detected for '{goal}', replan requested."
        return "Success" if success else "Failure"

    def start(self) -> None:
        def loop():
            while not self.bus.stopped:
                msg = self.bus.receive("critic", timeout=0.5)
                if msg is None:
                    continue
                if msg.get("type") == SHUTDOWN:
                    break
                if msg.get("type") == "results":
                    self.run(msg["data"], msg.get("goal", ""))
        self._thread = threading.Thread(target=loop, daemon=True, name="CriticAgent")
        self._thread.start()

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "evaluate":
            return str(self.evaluate(args[0]))
        return f"CriticAgent - command '{command}' not implemented."

    def shutdown(self) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)