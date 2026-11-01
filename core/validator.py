import logging
from typing import Any, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_input(data: Dict[str, Any]) -> bool:
    """
    Basic input validator. Expand with real validation rules.
    """
    logger.info("Validating input: %s", data)
    # Example rule: must have 'text' field
    if "text" not in data:
        logger.error("Missing required 'text' field.")
        return False
    return True