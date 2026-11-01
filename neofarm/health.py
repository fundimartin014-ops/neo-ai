def check(symptom):
    if "cough" in symptom:
        return "Possible respiratory issue. Isolate animal."
    if "no appetite" in symptom:
        return "Possible illness. Monitor temperature."
    return "Monitor closely."
