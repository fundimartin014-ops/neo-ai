import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TranslateSkill:
    """
    Hybrid translate:
      1. Local LLM (Groq → OpenRouter → Ollama) — great for context and idioms
      2. MyMemory free API
    Order: LLM first (better quality), API as fallback.
    """

    MYMEMORY_API = "https://api.mymemory.translated.net/get"

    def __init__(self):
        pass

    _LANG_ALIASES = {
        "swahili": "sw", "kiswahili": "sw",
        "english": "en", "spanish": "es", "espanol": "es",
        "french": "fr", "german": "de", "italian": "it",
        "portuguese": "pt", "russian": "ru", "chinese": "zh",
        "japanese": "ja", "korean": "ko", "arabic": "ar",
        "hindi": "hi", "somali": "so", "amharic": "am",
    }

    def _normalize_lang(self, code):
        if not code:
            return "auto"
        c = str(code).lower().strip()
        return self._LANG_ALIASES.get(c, c)

    def _detect_source(self, text):
        """Resolve 'auto' to a 2-letter ISO code. MyMemory rejects
        'auto' but accepts real codes."""
        try:
            from langdetect import detect as _ld
            lang = _ld(text)
            if lang and 2 <= len(lang) <= 5:
                return lang
        except Exception:
            pass
        t = text.lower()
        if any(w in t for w in ("bonjour", "merci", "avec ", "pour ")):
            return "fr"
        if any(w in t for w in ("hola", "gracias", "como ", "pero ")):
            return "es"
        if any(w in t for w in ("hallo", "danke", "und ", "nicht ")):
            return "de"
        if any(w in t for w in ("habari", "asante", "jambo")):
            return "sw"
        return "en"

    def _llm_translate(self, text, src, tgt):
        try:
            from core.local_llm import LocalLLM
            llm = LocalLLM()
            system = (
                f"You are a professional translator. Translate the user's text "
                f"from {src} to {tgt}. Preserve meaning, tone, and formatting. "
                f"Output ONLY the translated text — no explanations, no quotes."
            )
            out = llm.generate(text, system=system, temperature=0.1, max_tokens=800)
            if out and len(out) > 0 and not out.startswith("[Neo]"):
                return out.strip()
        except Exception as e:
            logger.debug(f"translate: LLM failed: {e}")
        return None

    def _mymemory(self, text, src, tgt):
        try:
            r = requests.get(
                self.MYMEMORY_API,
                params={"q": text, "langpair": f"{src}|{tgt}"},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            translated = data.get("responseData", {}).get("translatedText")
            if translated:
                return translated
        except Exception as e:
            logger.debug(f"translate: MyMemory failed: {e}")
        return None

    def process(self, inputs: dict) -> dict:
        text = str(inputs.get("text", "")).strip()

        src = self._normalize_lang(inputs.get("src", "en"))
        tgt = self._normalize_lang(inputs.get("tgt", "es"))
        if not text:
            return {"error": "text is required"}
        # FIXED: resolve "auto" to a real ISO code before sending to MyMemory
        if src in ("auto", "autodetect", ""):
            src = self._detect_source(text)
            logger.info(f"TranslateSkill: resolved auto → {src}")

        if src == tgt:
            return {"translated": text, "src": src, "tgt": tgt, "method": "identity"}

        logger.info(f"TranslateSkill: {src}->{tgt} '{text[:60]}'")

        # FIXED: MyMemory first (deterministic), LLM second.
        # The LLM was hallucinating wrong languages for short codes
        # (e.g. "sw" → Korean) and returning gibberish.
        out = self._mymemory(text, src, tgt)
        if out:
            return {"translated": out, "src": src, "tgt": tgt, "method": "mymemory"}

        out = self._llm_translate(text, src, tgt)
        if out:
            return {"translated": out, "src": src, "tgt": tgt, "method": "llm"}


        return {"error": "All translation backends failed"}