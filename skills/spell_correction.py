import logging
import difflib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_DEFAULT_VOCAB = [
    "hello", "world", "python", "javascript", "computer", "network",
    "database", "function", "variable", "algorithm", "the", "and", "for",
    "you", "with", "this", "that", "have", "from", "they", "would", "there",
]


class SpellCorrectionSkill:
    """
    Hybrid spell correction:
      1. Try local/cloud LLM (handles context, grammar, proper nouns)
      2. Fall back to difflib against a vocabulary
    """

    def __init__(self, vocabulary=None):
        self.vocabulary = list(vocabulary) if vocabulary else list(_DEFAULT_VOCAB)

    def _llm_correct(self, text):
        try:
            from core.local_llm import LocalLLM
            llm = LocalLLM()
            system = (
                "Correct spelling, grammar, and punctuation. "
                "Preserve meaning, tone, and formatting. "
                "Output ONLY the corrected text."
            )
            out = llm.generate(text, system=system, temperature=0.1, max_tokens=600)
            if out and len(out) > 0 and not out.startswith("[Neo]"):
                return out.strip()
        except Exception as e:
            logger.debug(f"spell: LLM failed: {e}")
        return None

    def _difflib_correct(self, text, vocab):
        words = text.split()
        corrected = []
        for w in words:
            matches = difflib.get_close_matches(w.lower(), vocab, n=1, cutoff=0.75)
            corrected.append(matches[0] if matches else w)
        return " ".join(corrected)

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        if not text:
            return {"error": "text is required"}

        llm_out = self._llm_correct(text)
        if llm_out:
            logger.info(f"SpellCorrectionSkill (llm): '{text[:40]}' -> '{llm_out[:40]}'")
            return {"corrected": llm_out, "method": "llm"}

        vocab = inputs.get("vocabulary") or self.vocabulary
        out = self._difflib_correct(text, vocab)
        logger.info(f"SpellCorrectionSkill (difflib): '{text[:40]}' -> '{out[:40]}'")
        return {"corrected": out, "method": "difflib"}