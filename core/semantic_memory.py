import json
from pathlib import Path
from sentence_transformers import SentenceTransformer, util
from difflib import SequenceMatcher

MEMORY_FILE = Path("core/semantic_memory.json")

model = None


def _ensure_model():
    global model
    if model is not None:
        return True
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        return True
    except Exception:
        model = None
        return False

def load_memory():
    if not MEMORY_FILE.exists():
        return []
    with open(MEMORY_FILE,"r",encoding="utf-8") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)

def store(text, response, **meta):

    memory = load_memory()

    embedding = _ensure_model() and model.encode(text).tolist()

    memory.append({
        "text": text,
        "response": response,
        "embedding": embedding or [],
        "meta": meta
    })

    save_memory(memory)

def remember(text, response=None, **meta):
    store(text, response if response is not None else text, **meta)


def search(query, top_k=3):

    memory = load_memory()

    if not memory:
        return []

    if not _ensure_model():
        ranked = sorted(
            memory,
            key=lambda item: SequenceMatcher(None, query.lower(), str(item.get("text", "")).lower()).ratio(),
            reverse=True,
        )
        return ranked[:top_k]

    query_vec = model.encode(query)

    scores = []

    for item in memory:

        if not item.get("embedding"):
            continue
        sim = util.cos_sim(query_vec, item["embedding"]).item()

        scores.append((sim, item))

    scores.sort(reverse=True)

    return [s[1] for s in scores[:top_k]]
