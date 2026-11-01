import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DateSkill:
    """Returns today's date, or tomorrow's / yesterday's on request."""

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        query = str(inputs.get("query", "today")).lower().strip()
        today = datetime.now().date()

        if "tomorrow" in query:
            target = today + timedelta(days=1)
        elif "yesterday" in query:
            target = today - timedelta(days=1)
        else:
            target = today

        result = target.isoformat()
        logger.info(f"DateSkill returns: {result}")
        return {"date": result}
