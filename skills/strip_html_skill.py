import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StripHTMLSkill:
    """
    Strips HTML tags from a text string.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        text = inputs.get("html", "")
        stripped = re.sub(r"<[^>]*>", "", text)
        logger.info(f"StripHTMLSkill: '{text[:40]}' -> '{stripped[:40]}'")
        return {"result": stripped}