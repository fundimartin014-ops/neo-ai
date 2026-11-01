import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import tiktoken  # type: ignore
    _ENC = tiktoken.get_encoding("cl100k_base")
    _HAS_TIKTOKEN = True
except Exception:
    _HAS_TIKTOKEN = False


class TokenCountSkill:
    """
    Token count:
      - tiktoken cl100k_base (OpenAI-compatible) if available
      - word + character counts as fallback
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        if not text:
            return {"error": "text is required"}

        if _HAS_TIKTOKEN:
            try:
                tokens = _ENC.encode(text)
                return {
                    "tokens": len(tokens),
                    "method": "tiktoken_cl100k_base",
                    "words": len(text.split()),
                    "characters": len(text),
                }
            except Exception as e:
                logger.debug(f"token_count: tiktoken failed: {e}")

        return {
            "tokens": len(text.split()),  # rough estimate
            "method": "word_estimate",
            "words": len(text.split()),
            "characters": len(text),
        }