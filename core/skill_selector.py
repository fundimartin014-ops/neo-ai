try:
    from skills import device_skill
except ImportError:
    device_skill = None


def select_skill(query):
    q = query.lower()
    if device_skill and any(term in q for term in ("turn on", "turn off", "temperature")):
        return device_skill
    return None
