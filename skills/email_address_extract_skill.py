import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailAddressExtractSkill:
    """
    Extracts all email addresses from input text using regex.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        emails = re.findall(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", text)
        logger.info(f"EmailExtraction: found {len(emails)} addresses.")
        return {"emails": emails}