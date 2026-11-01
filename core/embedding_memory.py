import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MEMORY_FILE = "core/memory.json"

class EmbeddingMemory:

    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.index = faiss.IndexFlatL2(384)
        self.texts = []
        self.meta = []

        self.load()

    def load(self):
        if not os.path.exists(MEMORY_FILE):
            return

        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)

        for item in data:
            text = item.get("query", "")
            if text:
                vec = self.model.encode([text])[0]
                self.index.add(np.array([vec]).astype("float32"))
                self.texts.append(text)
                self.meta.append(item)

    def add(self, text, meta):
        vec = self.model.encode([text])[0]
        self.index.add(np.array([vec]).astype("float32"))
        self.texts.append(text)
        self.meta.append(meta)

    def search(self, query, k=3):
        if len(self.texts) == 0:
            return []

        vec = self.model.encode([query])[0]
        D, I = self.index.search(np.array([vec]).astype("float32"), k)

        results = []
        for idx in I[0]:
            if idx < len(self.meta):
                results.append(self.meta[idx])

        return results