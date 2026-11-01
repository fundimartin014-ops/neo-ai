import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from difflib import SequenceMatcher

MEMORY_FILE = "core/embedding_memory.json"


class EmbeddingEngine:

    def __init__(self):
        self.model = None
        self.index = faiss.IndexFlatL2(384)

        self.texts = []
        self.responses = []

        self._load_memory()

    def _ensure_model(self):
        if self.model is not None:
            return True
        try:
            self.model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            return True
        except Exception:
            self.model = None
            return False

    # ============================================
    # LOAD MEMORY
    # ============================================
    def _load_memory(self):

        if not os.path.exists(MEMORY_FILE):
            return

        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)

        for item in data:
            query = item["query"]
            response = item["response"]

            self.texts.append(query)
            self.responses.append(response)

        if self._ensure_model():
            for query in self.texts:
                vec = self.model.encode([query])[0].astype("float32")
                self.index.add(np.array([vec]))

    # ============================================
    # STORE
    # ============================================
    def store(self, query, response):

        if self._ensure_model():
            vec = self.model.encode([query])[0].astype("float32")
            self.index.add(np.array([vec]))

        self.texts.append(query)
        self.responses.append(response)

        self._save()

    # ============================================
    # SEARCH
    # ============================================
    def search(self, query, k=3):

        if len(self.texts) == 0:
            return []

        if not self._ensure_model() or self.index.ntotal == 0:
            ranked = sorted(
                zip(self.texts, self.responses),
                key=lambda item: SequenceMatcher(None, query.lower(), item[0].lower()).ratio(),
                reverse=True,
            )
            return [response for _, response in ranked[:k]]

        vec = self.model.encode([query])[0].astype("float32")

        D, I = self.index.search(np.array([vec]), min(k, self.index.ntotal))

        results = []

        for idx in I[0]:
            if idx < len(self.responses):
                results.append(self.responses[idx])

        return results

    # ============================================
    # SAVE
    # ============================================
    def _save(self):

        data = []

        for q, r in zip(self.texts, self.responses):
            data.append({"query": q, "response": r})

        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
