WAKE_WORDS = ["neo", "hey neo", "ok neo"]

def detect(text):
    text = text.lower()
    return any(word in text for word in WAKE_WORDS)
