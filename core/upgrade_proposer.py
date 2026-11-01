from core.quality_monitor import low_confidence_log

def propose():
    proposals = []

    for q, a, score in low_confidence_log[-5:]:
        proposals.append({
            "issue": q,
            "problem": "Low confidence answer",
            "suggestion": "Improve knowledge or add training data"
        })

    return proposals
