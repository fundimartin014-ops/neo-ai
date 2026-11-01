import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileReadSkill:
    """
    Stub skill: Given a filename, returns file content (with safety).
    Expand with path whitelists and max size for production!
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        filename = inputs.get("filename", "")
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read(1024*32) # Limit to 32K for safety
            logger.info("FileReadSkill read file: %s", filename)
            return {"content": content}
        except Exception as e:
            logger.error("FileReadSkill error: %s", e)
            return {"error": str(e)}