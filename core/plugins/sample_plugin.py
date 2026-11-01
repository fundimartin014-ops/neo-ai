import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    """
    Stub plugin class.
    Override run() to define plugin startup behavior.
    """

    def __init__(self):
        pass

    def run(self):
        """
        Startup hook for the plugin. Called automatically by launcher.
        """
        logger.info("Sample plugin run() executed.")