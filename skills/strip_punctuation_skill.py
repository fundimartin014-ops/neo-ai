import logging
import string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StripPunctuationSkill:
    """
    Removes all punctuation from a text string.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        table = str.maketrans('', '', string.punctuation)
        result = text.translate(table)
        logger.info(f"StripPunctuationSkill: '{text}' -> '{result}'")
        return {"result": result}