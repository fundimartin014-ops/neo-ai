import logging
import os
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    def __init__(self):
        # Free push notifications via ntfy.sh. No signup, no API key.
        self.topic = os.getenv("NTFY_TOPIC", "neo-fundi-alerts")
        self.url = f"https://ntfy.sh/{self.topic}"
        logger.info(f"[Notification] ntfy.sh topic: {self.topic}")

    def run(self):
        logger.info("Notification plugin ready. Use notify(msg).")

    def notify(self, message, title="Neo Alert", priority="default"):
        """
        Send free push notification via ntfy.sh.
        priority: min, low, default, high, urgent
        """
        try:
            r = requests.post(
                self.url,
                data=message.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": "robot,warning"
                },
                timeout=10
            )
            if r.status_code == 200:
                logger.info("[Notification] Sent successfully.")
                return True
            else:
                logger.warning(f"[Notification] Failed: HTTP {r.status_code}")
                return False
        except Exception as e:
            logger.error(f"[Notification] Error: {e}")
            return False