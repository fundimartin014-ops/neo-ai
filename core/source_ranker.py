def rank_source(text):

    text = text.lower()

    if ".gov" in text:
        return 1.5
    if ".edu" in text:
        return 1.4
    if "wikipedia" in text:
        return 1.3
    if "news" in text:
        return 1.2

    return 1.0