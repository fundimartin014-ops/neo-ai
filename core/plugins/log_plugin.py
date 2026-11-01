import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    """
    Logging plugin example. Customize as needed.
    """

    def __init__(self, log_message: str = "Plugin loaded!"):
        self.log_message = log_message

    def run(self):
        logger.info(f"Plugin message: {self.log_message}")