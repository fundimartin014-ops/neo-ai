import heapq
import itertools
from typing import Any, List, Tuple
from agents.base_agent import BaseAgent

class PriorityQueueAgent(BaseAgent):
    name = "PriorityQueueAgent"
    capabilities = ("queue",)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.queue: List[Tuple[int, int, Any]] = []
        self._counter = itertools.count()

    def run(self, priority: int, item: Any) -> str:
        heapq.heappush(self.queue, (priority, next(self._counter), item))
        return f"Task queued with priority {priority}."

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "next":
            if not self.queue:
                return "Queue empty."
            _, _, item = heapq.heappop(self.queue)
            return f"Next up: {item}"
        if command == "size":
            return str(len(self.queue))
        return f"PriorityQueueAgent - command '{command}' not implemented."