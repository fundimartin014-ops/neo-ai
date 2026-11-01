import logging
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CounterSkill:
    """
    Counts occurrence frequency of words or list items.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        data = inputs.get("data")
        if isinstance(data, str):
            items = data.split()
        elif isinstance(data, list):
            items = data
        else:
            logger.error("CounterSkill: Invalid input type.")
            return {"error": "Input must be a string or list"}
        counts = dict(Counter(items))
        logger.info(f"CounterSkill: {counts}")
        return {"counts": counts}