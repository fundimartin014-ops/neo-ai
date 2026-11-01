from typing import Any, Callable, Dict, List
from agents.base_agent import BaseAgent

class EventDispatchAgent(BaseAgent):
    name = "EventDispatchAgent"
    capabilities = ("subscribe", "publish")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, handler: Callable) -> None:
        self.subscribers.setdefault(event_name, []).append(handler)
        self.logger.info("subscribed %s to '%s'", handler, event_name)

    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        if event_name in self.subscribers:
            self.subscribers[event_name] = [h for h in self.subscribers[event_name] if h is not handler]

    def run(self, event_name: str, data: Any = None) -> str:
        handlers = list(self.subscribers.get(event_name, []))
        self.logger.info("dispatching '%s' to %d handler(s)", event_name, len(handlers))
        for h in handlers:
            try:
                h(data)
            except Exception as e:
                self.logger.exception("handler failed for %s: %s", event_name, e)
        return f"Event '{event_name}' dispatched."

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "list":
            return str({k: len(v) for k, v in self.subscribers.items()})
        return self.run(command, *args)