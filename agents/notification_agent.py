from typing import Any, Callable, List
from agents.base_agent import BaseAgent
from agents.notifiers import notify_brief

class NotificationAgent(BaseAgent):
    name = "NotificationAgent"
    capabilities = ("notify",)

    def __init__(self, sender: Callable[[str], None] = None, **kw):
        super().__init__(**kw)
        self.sender = sender or (lambda text: self.logger.info("NOTIFY: %s", text))
        self.sent: List[str] = []

    def run(self, notification_text: str) -> str:
        import asyncio
        self.sent.append(notification_text)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run,
                                notify_brief("Neo", notification_text)).result()
            else:
                loop.run_until_complete(notify_brief("Neo", notification_text))
        except RuntimeError:
            asyncio.run(notify_brief("Neo", notification_text))
        except Exception as e:
            self.logger.warning("notification failed: %s", e)
        return f"Notification sent: {notification_text}"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "history":
            return "\n".join(self.sent) if self.sent else "(none)"
        return f"NotificationAgent - command '{command}' not implemented."