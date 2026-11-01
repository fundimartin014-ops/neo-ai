import time
from core.semantic_memory import remember

def store(text, source, confidence=0.8):
    entry = f"{text} | confidence:{confidence} | time:{time.time()}"
    remember(entry, source)
