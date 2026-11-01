import json
import os
from core.memory import search_knowledge

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "../../memory.json")

def load_memory():
    """Load memory entries as a list."""
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_memory(data):
    """Save memory entries."""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def search(query):
    """Search memory.json for matching entries."""
    results = search_knowledge(query)
    return [{"text": r, "source": "memory"} for r in results]

def remember(input_text, response_text, source="manual"):
    """Store a new memory entry, skip duplicates."""
    memory = load_memory()

    # Skip exact duplicates
    if any(m.get("text") == response_text for m in memory):
        return

    entry = {"text": response_text, "source": source}
    memory.append(entry)
    save_memory(memory)
