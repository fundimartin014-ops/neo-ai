# =====================================================================
# core/memory.py
# UNIFIED MEMORY INTERFACE
# =====================================================================

import json
import os
import hashlib

# In-memory store
_memory_store = []
_trained_pdfs = set()

def remember(input_text, response=None, source="unknown", meta=None):
    """Store a memory entry. If response is None, input_text is treated as the response."""
    entry = {
        "input_text": input_text,
        "response": response if response is not None else input_text,
        "source": source,
        "meta": meta or {},
    }
    _memory_store.append(entry)
    # Persist to JSONL
    try:
        with open("memory.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except:
        pass

def search_knowledge(query):
    """Search stored memories for query matches."""
    results = []
    query_lower = query.lower()
    # Search in-memory
    for entry in _memory_store:
        if query_lower in str(entry.get("input_text", "")).lower():
            results.append(entry)
    # Search from file
    try:
        if os.path.exists("memory.json"):
            with open("memory.json", "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if query_lower in str(entry.get("input_text", "")).lower():
                            results.append(entry)
                    except:
                        pass
    except:
        pass
    return results

def reinforce(input_text, response):
    """Mark a memory as reinforced/verified."""
    pass

def penalize(input_text, response):
    """Mark a memory as incorrect."""
    pass

def store_correction(input_text, correct_response):
    """Store a human correction."""
    remember(input_text, correct_response, source="human_correction", meta={"verified": True})

def is_pdf_trained(pdf_id):
    """Check if a PDF has already been trained."""
    return pdf_id in _trained_pdfs

def mark_pdf_trained(pdf_id, filename=""):
    """Mark a PDF as trained."""
    _trained_pdfs.add(pdf_id)
    # Persist to file
    try:
        with open("trained_pdfs.json", "a", encoding="utf-8") as f:
            f.write(json.dumps({"pdf_id": pdf_id, "filename": filename}) + "\n")
    except:
        pass