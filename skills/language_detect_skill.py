import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from langdetect import detect as _ld_detect  # type: ignore
    _HAS_LANGDETECT = True
except ImportError:
    _HAS_LANGDETECT = False

_SCRIPT_RANGES = [
    ("zh", r"[\u4e00-\u9fff]"), ("ar", r"[\u0600-\u06ff]"),
    ("ru", r"[\u0400-\u04ff]"), ("el", r"[\u0370-\u03ff]"),
    ("he", r"[\u0590-\u05ff]"), ("hi", r"[\u0900-\u097f]"),
    ("ja", r"[\u3040-\u309f\u30a0-\u30ff]"), ("ko", r"[\uac00-\ud7af]"),
]


class LanguageDetectSkill:
    """
    Hybrid language detection:
      1. langdetect (fast, statistically strong)
      2. LLM (for short or mixed text)
      3. Script heuristics (for non-Latin scripts)
    """

    def __init__(self):
        pass

    def _llm(self, text):
        try:
            from core.local_llm import LocalLLM
            llm = LocalLLM()
            system = (
                "Detect the language of the user's text. "
                "Output ONLY the ISO 639-1 code (e.g. 'en', 'es', 'zh'). "
                "No prose, no explanation."
            )
            out = llm.generate(text, system=system, temperature=0.0, max_tokens=10)
            if out:
                code = out.strip().lower()[:2]
                if code.isalpha():
                    return code
        except Exception as e:
            logger.debug(f"langdetect: LLM failed: {e}")
        return None

    def process(self, inputs: dict) -> dict:
        text = str(inputs.get("text", "")).strip()
        if not text:
            return {"error": "text is required"}

        # 1. Script check — deterministic for non-Latin
        for lang, pat in _SCRIPT_RANGES:
            if re.search(pat, text):
                return {"detected_language": lang, "method": "script"}

        # 2. Short Latin text — language-specific keyword hints
        t = text.lower()
        _HINTS = [
            ("fr", ("bonjour", "merci", "le ", "la ", "avec ", "pour ", "oui")),
            ("es", ("hola", "gracias", "el ", "los ", "como ", "pero ", "mundo")),
            ("de", ("hallo", "danke", "der ", "die ", "das ", "und ", "nicht")),
            ("it", ("ciao", "grazie", "il ", "la ", "con ", "per ")),
            ("pt", ("olá", "obrigado", "com ", "para ", "não ")),
            ("sw", ("habari", "asante", "jambo", "kwa ")),
        ]
        if len(text) < 40:
            for lang, hints in _HINTS:
                if any(h in t for h in hints):
                    return {"detected_language": lang, "method": "keyword_hint"}

        # 3. Long Latin text — langdetect with mode voting
        if _HAS_LANGDETECT and len(text) >= 20:
            try:
                from collections import Counter
                votes = []
                for _ in range(5):
                    try:
                        votes.append(_ld_detect(text))
                    except Exception:
                        pass
                if votes:
                    mode = Counter(votes).most_common(1)[0][0]
                    if mode:
                        return {"detected_language": mode, "method": "langdetect_vote"}
            except Exception:
                pass

        # 4. LLM fallback (short text only)
        if len(text) < 40:
            llm_result = self._llm(text)
            if llm_result:
                return {"detected_language": llm_result, "method": "llm"}

        return {"detected_language": "en", "method": "default"}
