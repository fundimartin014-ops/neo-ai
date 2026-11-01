import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RandomSkill:
    """
    Provides random numbers or choices from a list.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        kind = inputs.get("kind", "int")
        if kind == "int":
            start = int(inputs.get("start", 0))
            end = int(inputs.get("end", 100))
            result = random.randint(start, end)
        elif kind == "choice":
            options = inputs.get("options", [])
            result = random.choice(options) if options else None
        else:
            logger.error("Unknown kind for RandomSkill: %s", kind)
            return {"error": "Unknown kind"}
        logger.info("RandomSkill produced: %s", result)
        return {"result": result}