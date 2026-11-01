import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup  # type: ignore
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False


class HTMLStripSkill:
    """
    Strip HTML, preferring BeautifulSoup (robust) and falling back to regex.
    Also decodes common HTML entities when bs4 is missing.
    """

    def __init__(self):
        pass

    def process(self, inputs: dict) -> dict:
        html = inputs.get("html", "")
        if not html:
            return {"error": "html is required"}

        if _HAS_BS4:
            try:
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(separator=" ")
                text = re.sub(r"\s+", " ", text).strip()
                logger.info(f"HTMLStripSkill (bs4): {len(html)} -> {len(text)} chars")
                return {"text": text, "method": "bs4"}
            except Exception as e:
                logger.debug(f"html_strip: bs4 failed: {e}")

        # Regex fallback + entity decode
        import html as _html
        cleaned = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.I)
        cleaned = re.sub(r"<style.*?</style>", "", cleaned, flags=re.DOTALL | re.I)
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        cleaned = _html.unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        logger.info(f"HTMLStripSkill (regex): {len(html)} -> {len(cleaned)} chars")
        return {"text": cleaned, "method": "regex"}