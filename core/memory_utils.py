from core.memory import remember, search_knowledge
from core.utils import clean_text, summarize_text, rank_results

MAX_STORE_LENGTH = 500
MAX_RETURN_LENGTH = 800
MAX_SUMMARY_SENTENCES = 3
TOP_RESULTS_TO_MERGE = 3

def remember_input(text, source="unknown"):
    """Clean, summarize, truncate, then store any input from any source."""
    text = clean_text(text)
    text = summarize_text(text, max_sentences=MAX_SUMMARY_SENTENCES)
    text = text[:MAX_STORE_LENGTH]
    remember(text, source)

def get_fallback(user_input):
    """Return ranked, merged, summarized answer from memory."""
    results = search_knowledge(user_input)
    results = rank_results(user_input, results)

    if not results:
        return "I don't know that yet."

    # Merge by topic from multiple sources
    merged_texts = []
    sources_seen = set()
    for r in results[:TOP_RESULTS_TO_MERGE*2]:
        if "pdf_knowledge" in r and "pdf_knowledge" not in sources_seen:
            merged_texts.append(r)
            sources_seen.add("pdf_knowledge")
        elif "web" in r and "web" not in sources_seen:
            merged_texts.append(r)
            sources_seen.add("web")
        elif "manual" in r and "manual" not in sources_seen:
            merged_texts.append(r)
            sources_seen.add("manual")

    merged = " ".join(merged_texts[:TOP_RESULTS_TO_MERGE])
    merged = summarize_text(merged, max_sentences=MAX_SUMMARY_SENTENCES)
    merged = clean_text(merged)
    merged = merged[:MAX_RETURN_LENGTH]

    remember(f"Q: {user_input}\nA: {merged}", source="fallback")
    return merged
