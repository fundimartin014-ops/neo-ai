import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Plugin:
    """
    Scheduler plugin stub. Use APScheduler or Celery for real job scheduling.
    """

    def __init__(self):
        self.jobs = []

    def run(self):
        logger.info("Scheduler plugin started (stub mode).")
        # Real implementations would trigger periodic/background jobs

    def schedule(self, job, when):
        self.jobs.append((job, when))
        logger.info(f"Job scheduled for {when}: {job}")