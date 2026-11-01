import re
from typing import List


class EntityExtractor:
    """Small entity extractor used by the legacy planning brain."""

    def extract(self, text: str) -> List[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", str(text))
        stop_words = {
            "a", "an", "and", "are", "for", "how", "is", "of", "the",
            "to", "what", "when", "where", "who", "why",
        }
        return [word for word in words if word.lower() not in stop_words]
