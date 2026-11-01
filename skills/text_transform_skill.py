import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextTransformSkill:
    """Transform text: upper, lower, reverse, title, swapcase, capitalize."""

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        operation = inputs.get("operation", "upper")

        if operation == "upper":
            result = text.upper()
        elif operation == "lower":
            result = text.lower()
        elif operation == "reverse":
            result = text[::-1]
        elif operation == "title":
            result = text.title()
        elif operation == "swapcase":
            result = text.swapcase()
        elif operation == "capitalize":
            result = text.capitalize()
        else:
            result = text

        logger.info("TextTransformSkill produced: %s", result)
        return {"result": result}
