import re

def clean_text(text):
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)  # collapse spaces/newlines
    text = re.sub(r'([!?.,])\1+', r'\1', text)  # remove repeated punctuation
    return text

def summarize_text(text, max_sentences=3):
    sentences = re.split(r'(?<=[.!?]) +', text)
    summary = ' '.join(sentences[:max_sentences])
    return summary

def rank_results(query, results):
    query_words = query.lower().split()
    scored = []
    for r in results:
        r_lower = r.lower()
        score = sum(r_lower.count(w) for w in query_words)
        scored.append((score, r))
    scored.sort(reverse=True)
    return [r for score, r in scored]
