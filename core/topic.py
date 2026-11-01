def detect_topic(text: str) -> str:
    """
    Classify the topic of a given text input.
    Returns one of: history, ai, technology, identity, general.
    """
    text = text.lower()
    if any(k in text for k in ["kenya", "history", "colonial", "empire", "africa"]):
        return "history"
    if any(k in text for k in ["ai", "artificial intelligence", "machine learning"]):
        return "ai"
    if any(k in text for k in ["software", "code", "computer", "python"]):
        return "technology"
    if any(k in text for k in ["who are you", "who created", "your name"]):
        return "identity"
    return "general"