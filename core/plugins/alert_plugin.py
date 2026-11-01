import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    """
    A stub for a plugin that would trigger application alerts/notifications.
    """

    def __init__(self, alert_message: str = "Default alert!"):
        self.alert_message = alert_message

    def run(self):
        logger.info(f"[ALERT PLUGIN] {self.alert_message}")