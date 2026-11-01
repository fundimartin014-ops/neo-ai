import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fallback_response(user_input: str) -> Optional[str]:
    """
    Stub fallback response.
    Replace with retrieval logic, e.g. default generative LLM, online search, or FAQ lookup.
    """
    logger.info("Handling fallback for: %s", user_input)
    # TODO: Integrate with default LLM, search API, or knowledge base
    return None  # Or return a string like "Sorry, I don't know."