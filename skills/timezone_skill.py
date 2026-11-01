import logging
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TimezoneSkill:
    """
    Returns the current time in a user-specified timezone.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        tz_name = inputs.get("timezone", "UTC")
        try:
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)
            result = now.strftime("%Y-%m-%d %H:%M:%S %Z")
            logger.info(f"TimezoneSkill: {result}")
            return {"time": result}
        except Exception as e:
            logger.error(f"TimezoneSkill error: {e}")
            return {"error": str(e)}