def reason(query, evidence=None):
    """
    Core reasoning engine.
    Combines evidence into a human-like response.
    """

    if not evidence:
        return "I don't have enough information yet."

    if isinstance(evidence, list):
        return evidence[0].get("text", "")[:800]

    return str(evidence)
