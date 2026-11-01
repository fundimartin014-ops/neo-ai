import re

def normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()
