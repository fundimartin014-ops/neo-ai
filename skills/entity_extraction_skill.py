import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import spacy  # type: ignore
    try:
        _NLP = spacy.load("en_core_web_sm")
    except Exception:
        _NLP = None
except ImportError:
    _NLP = None


class EntityExtractionSkill:
    """
    Hybrid NER:
      1. spaCy (fast, structured)
      2. LLM (better for edge cases, custom entity types)
      3. Regex fallback (capitalized words)
    """

    def __init__(self):
        pass

    def _spacy(self, text):
        if _NLP is None:
            return None
        try:
            doc = _NLP(text)
            ents = [{"text": e.text, "label": e.label_} for e in doc.ents]
            if ents:
                return ents
        except Exception as e:
            logger.debug(f"entity: spacy failed: {e}")
        return None

    def _llm(self, text):
        try:
            from core.local_llm import LocalLLM
            llm = LocalLLM()
            system = (
                "Extract named entities. Output ONLY a JSON array of objects "
                'with keys "text" and "label" (PERSON, ORG, LOC, DATE, MISC). '
                "No prose, no markdown."
            )
            out = llm.generate(text, system=system, temperature=0.1, max_tokens=500)
            if out and out.strip().startswith("["):
                import json
                return json.loads(out.strip())
        except Exception as e:
            logger.debug(f"entity: LLM failed: {e}")
        return None

    def _regex(self, text):
        return [{"text": m, "label": "MISC"}
                for m in re.findall(r"\b[A-Z][a-z]{2,}\b", text)]

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        if not text:
            return {"error": "text is required"}

        ents = self._spacy(text)
        if ents:
            return {"entities": ents, "method": "spacy"}

        ents = self._llm(text)
        if ents:
            return {"entities": ents, "method": "llm"}

        return {"entities": self._regex(text), "method": "regex"}