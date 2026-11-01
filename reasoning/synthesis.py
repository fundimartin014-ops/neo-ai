def synthesize_answer(query, evidence):
    top = evidence[:3]
    answer = ""

    for e in top:
        answer += e["text"][:400] + "\n\n"

    return answer.strip()
