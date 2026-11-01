import logging
import re
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on",
    "at", "by", "for", "with", "is", "are", "was", "were", "be", "been",
    "this", "that", "these", "those", "it", "its", "as", "from", "has",
    "have", "had", "do", "does", "did", "will", "would", "can", "could",
}


class SummarySkill:
    """
    Hybrid summary:
      1. Try cloud LLM for abstractive summary (best quality)
      2. Fall back to extractive frequency-based summary (offline)
    """

    def __init__(self):
        pass

    def _llm_summary(self, text, max_words=120):
        try:
            from core.local_llm import LocalLLM
            llm = LocalLLM()
            system = (
                "Summarize the user's text in clear, factual prose. "
                f"Aim for under {max_words} words. Preserve key names, numbers, and dates."
            )
            out = llm.generate(text, system=system, temperature=0.2, max_tokens=400)
            if out and len(out) > 3 and not out.startswith("[Neo]"):
                return out
        except Exception as e:
            logger.debug(f"summary: LLM failed: {e}")
        return None

    def _extractive_summary(self, text, max_sentences):
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if len(sentences) <= max_sentences:
            return text
        words = re.findall(r"\b[a-z]+\b", text.lower())
        freq = Counter(w for w in words if w not in _STOP and len(w) > 2)
        scored = []
        for i, s in enumerate(sentences):
            sw = re.findall(r"\b[a-z]+\b", s.lower())
            score = sum(freq.get(w, 0) for w in sw) / (len(sw) or 1)
            scored.append((score, i, s))
        top = sorted(scored, key=lambda x: x[0], reverse=True)[:max_sentences]
        top_sorted = sorted(top, key=lambda x: x[1])
        return " ".join(s for _, _, s in top_sorted)

    def process(self, inputs: dict) -> dict:
        text = str(inputs.get("text", "")).strip()
        if not text:
            return {"error": "text is required"}

        try:
            max_sentences = int(inputs.get("max_sentences", 3))
        except (TypeError, ValueError):
            max_sentences = 3
        max_sentences = max(1, min(max_sentences, 10))

        # Short texts don't need summarization
        if len(text.split()) < 80:
            return {"summary": text, "method": "passthrough"}

        llm_sum = self._llm_summary(text)
        if llm_sum:
            return {"summary": llm_sum, "method": "llm_abstractive"}

        ext = self._extractive_summary(text, max_sentences)
        return {"summary": ext, "method": "extractive"}