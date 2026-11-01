import logging
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import dateparser  # type: ignore
    _HAS_DATEPARSER = True
except ImportError:
    _HAS_DATEPARSER = False


class DatetimeParseSkill:
    """
    Hybrid date parsing:
      1. dateparser (natural language: "next friday at 3pm")
      2. LLM (rare formats)
      3. Regex (ISO 8601 only)
    """

    def __init__(self):
        pass

    def _dateparser(self, text):
        if not _HAS_DATEPARSER:
            return None
        try:
            dt = dateparser.parse(text)
            if dt:
                return dt.isoformat()
        except Exception as e:
            logger.debug(f"datetime: dateparser failed: {e}")
        return None

    def _llm(self, text):
        try:
            from core.local_llm import LocalLLM
            llm = LocalLLM()
            system = (
                "Parse the natural-language date/time in the user's text. "
                "Output ONLY an ISO 8601 datetime string (YYYY-MM-DDTHH:MM:SS). "
                "If ambiguous, assume today. No prose."
            )
            out = llm.generate(text, system=system, temperature=0.0, max_tokens=30)
            if out:
                candidate = out.strip()
                try:
                    datetime.fromisoformat(candidate.replace("Z", ""))
                    return candidate
                except ValueError:
                    pass
        except Exception as e:
            logger.debug(f"datetime: LLM failed: {e}")
        return None

    def _regex(self, text):
        m = re.search(r"\b(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?)\b", text)
        return m.group(1) if m else None

    def process(self, inputs: dict) -> dict:
        text = str(inputs.get("text", "")).strip()
        if not text:
            return {"error": "text is required"}

        for name, fn in (("dateparser", self._dateparser),
                         ("llm", self._llm),
                         ("regex", self._regex)):
            try:
                dt = fn(text)
                if dt:
                    return {"datetime": dt, "method": name}
            except Exception as e:
                logger.debug(f"datetime: {name} failed: {e}")

        return {"error": "Could not parse a date from input"}