import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Try NLTK's full English stopword list (~180 words). Falls back to a
# small built-in set if NLTK or the corpus data isn't installed.
try:
    from nltk.corpus import stopwords as _nltk_sw
    _STOPWORDS = set(_nltk_sw.words("english"))
    _STOPWORD_SOURCE = "nltk"
except Exception:
    _STOPWORDS = {
        "the", "and", "a", "an", "to", "of", "in", "on", "at", "by",
        "is", "are", "was", "were", "be", "been", "being",
        "you", "your", "yours", "i", "me", "my", "we", "our", "us",
        "that", "this", "these", "those", "it", "its",
        "for", "with", "from", "as", "but", "or", "if", "then",
        "do", "does", "did", "have", "has", "had",
        "will", "would", "can", "could", "should", "may", "might",
        "not", "no", "so", "than", "too", "very",
    }
    _STOPWORD_SOURCE = "builtin"


class RemoveStopwordsSkill:
    """
    Removes common stopwords from English text.

    Stopword source:
      - NLTK English corpus (~180 words) if installed
      - Built-in ~60-word set otherwise
    Case-insensitive. Preserves order and remaining tokens.
    """

    def __init__(self):
        logger.debug(f"RemoveStopwordsSkill using {_STOPWORD_SOURCE} stopwords ({len(_STOPWORDS)} words)")

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        if not text:
            return {"error": "text is required"}

        # Allow caller to extend/override stopwords per call
        extra = inputs.get("extra_stopwords") or []
        stop = _STOPWORDS | set(w.lower() for w in extra)

        # Preserve original case and punctuation-adjacent tokens by only
        # filtering whole whitespace-separated words.
        words = text.split()
        kept = [w for w in words if w.lower().strip(".,!?;:\"'()[]{}") not in stop]
        result = " ".join(kept)

        logger.info(
            f"RemoveStopwordsSkill ({_STOPWORD_SOURCE}): "
            f"{len(words)} -> {len(kept)} words"
        )
        return {
            "result": result,
            "removed_count": len(words) - len(kept),
            "source": _STOPWORD_SOURCE,
        }