import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RegexExtractionSkill:
    """
    Regex extract + replace.
    Inputs:
      text     (required)
      pattern  (required)
      flags    (optional: i, m, s, x — string or list)
      replace  (optional: if provided, returns replaced text)
    """

    def __init__(self):
        pass

    def _flags(self, flag_spec):
        f = 0
        if not flag_spec:
            return f
        if isinstance(flag_spec, str):
            flag_spec = [flag_spec]
        for fl in flag_spec:
            f |= {
                "i": re.IGNORECASE,
                "m": re.MULTILINE,
                "s": re.DOTALL,
                "x": re.VERBOSE,
            }.get(fl.lower(), 0)
        return f

    def process(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        pattern = inputs.get("pattern", "")
        if not pattern:
            return {"error": "Please provide a regex pattern"}

        flags = self._flags(inputs.get("flags"))

        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}

        replacement = inputs.get("replace")
        if replacement is not None:
            try:
                result = compiled.sub(replacement, text)
                logger.info(f"RegexExtractionSkill: replaced → {len(result)} chars")
                return {"result": result, "matches": len(compiled.findall(text))}
            except Exception as e:
                return {"error": f"Replace failed: {e}"}

        matches = compiled.findall(text)
        logger.info(f"RegexExtractionSkill found {len(matches)} matches")
        # If groups are present, findall returns tuples
        if matches and isinstance(matches[0], tuple):
            matches = [list(m) for m in matches]
        return {"matches": matches, "count": len(matches)}