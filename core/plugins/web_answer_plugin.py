def answer(self, text):

    result = search_web(text)

    if not result:
        return None

    raw_text = result["text"]
    sources = result["sources"]

    short = self.generate_short_answer(text, raw_text)
    confidence = self.calculate_confidence(raw_text)

    citation_line = "Sources: " + ", ".join(sources[:3])

    remember(
        input_text=f"[WEB ANSWER] {text}",
        response=short,
        source="web",
        meta={"confidence": confidence}
    )

    return (
        f"{short}\n\n"
        f"{citation_line}\n"
        f"Confidence: {confidence}%"
    )
