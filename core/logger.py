from loguru import logger

logger.add(
    "neo.log",
    rotation="5 MB",
    level="INFO"
)

def log_info(message: str) -> None:
    """Log an informational message."""
    logger.info(message)

def log_error(message: str) -> None:
    """Log an error message."""
    logger.error(message)