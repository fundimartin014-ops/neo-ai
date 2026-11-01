low_confidence_log = []

def evaluate(answer):
    score = 1.0
    if len(answer) < 30:
        score -= 0.4
    if "I don't know" in answer:
        score -= 0.5
    return max(score, 0.0)

def record(query, answer):
    score = evaluate(answer)
    if score < 0.6:
        low_confidence_log.append((query, answer, score))
    return score
