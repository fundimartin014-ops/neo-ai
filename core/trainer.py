import time
from core.web_fallback import fetch_web_answers
from core.semantic_memory import remember, search

def self_learn(user_input):
    """If Neo doesn't know, search web or offline datasets and learn automatically."""
    results = search(user_input)
    if results:
        return results[0]

    # Unknown query → fetch web answers
    web_answers = fetch_web_answers(user_input)
    for answer in web_answers:
        remember(f"Q: {user_input}\nA: {answer}", source="auto_web")
    
    # Retry after learning
    results = search(user_input)
    return results[0] if results else "I still don't know that yet."
