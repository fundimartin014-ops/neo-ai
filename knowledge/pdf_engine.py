import os
import json

PDF_INDEX_FILE = "processed_pdfs.json"

def search_pdf(query, topic=None):
    if not os.path.exists(PDF_INDEX_FILE):
        return []

    with open(PDF_INDEX_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []

    for item in data:
        text = item.get("text", "")
        if query.lower() in text.lower():
            results.append({
                "text": text,
                "source": "pdf",
                "meta": {
                    "file": item.get("file"),
                    "page": item.get("page")
                }
            })

    return results
