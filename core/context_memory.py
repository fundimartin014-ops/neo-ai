MAX_CONTEXT = 5
conversation_context = []

def add_context(user_input, response):
    """Keep last n exchanges in memory."""
    conversation_context.append({"user": user_input, "response": response})
    if len(conversation_context) > MAX_CONTEXT:
        conversation_context.pop(0)

def get_context_summary():
    """Return combined context for fallback queries."""
    return " ".join([f"User: {c['user']} AI: {c['response']}" for c in conversation_context])
