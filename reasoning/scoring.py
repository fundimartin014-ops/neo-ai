def score_evidence(query, evidence):
    for e in evidence:
        e["score"] = min(1.0, len(e["text"]) / 500)
    return sorted(evidence, key=lambda x: x["score"], reverse=True)
