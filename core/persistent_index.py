"""
core/persistent_index.py
Persistent FAISS vector store with metadata.
Survives reboots — no more re-chunking on every startup.
"""

import os
import pickle
import hashlib
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("[PersistentFAISS] faiss not installed. Using mock index.")


class PersistentFAISS:
    def __init__(self, dimension: int = 384, index_dir: str = "data/vector_store"):
        self.dimension = dimension
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.index_dir / "neo_index.faiss"
        self.meta_file = self.index_dir / "neo_metadata.pkl"
        self.seen_file = self.index_dir / "seen_hashes.pkl"
        self.index = None
        self.metadata: Dict[int, Dict] = {}
        self.seen_hashes: set = set()
        self.next_id = 0
        self._load()

    def _load(self):
        if not FAISS_AVAILABLE:
            self.index = None
            self.metadata = {}
            self.seen_hashes = set()
            return
        if self.index_file.exists() and self.meta_file.exists():
            try:
                self.index = faiss.read_index(str(self.index_file))
                with open(self.meta_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                if self.seen_file.exists():
                    with open(self.seen_file, 'rb') as f:
                        self.seen_hashes = pickle.load(f)
                self.next_id = max(self.metadata.keys(), default=-1) + 1
                print(f"[PersistentFAISS] Loaded {len(self.metadata)} vectors, {len(self.seen_hashes)} unique hashes")
            except Exception as e:
                print(f"[PersistentFAISS] Corrupt index, rebuilding: {e}")
                self._create_new()
        else:
            self._create_new()

    def _create_new(self):
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatIP(self.dimension)
        else:
            self.index = None
        self.metadata = {}
        self.seen_hashes = set()
        self.next_id = 0
        print("[PersistentFAISS] Created new index")

    def is_duplicate(self, text: str) -> bool:
        h = hashlib.md5(text.encode("utf-8")).hexdigest()
        return h in self.seen_hashes

    def add(self, vectors: np.ndarray, texts: List[str], sources: List[str],
            topics: Optional[List[str]] = None) -> int:
        if not FAISS_AVAILABLE or self.index is None:
            print("[PersistentFAISS] FAISS not available, skipping add")
            return 0
        if isinstance(vectors, list):
            vectors = np.array(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        faiss.normalize_L2(vectors)

        added = 0
        new_vectors = []
        new_ids = []
        for i, text in enumerate(texts):
            h = hashlib.md5(text.encode("utf-8")).hexdigest()
            if h in self.seen_hashes:
                continue
            self.seen_hashes.add(h)
            new_vectors.append(vectors[i])
            new_ids.append(self.next_id)
            self.metadata[self.next_id] = {
                "text": text,
                "source": sources[i] if i < len(sources) else "unknown",
                "topic": topics[i] if topics and i < len(topics) else "general",
                "hash": h,
                "added_at": datetime.now().isoformat()
            }
            self.next_id += 1
            added += 1

        if new_vectors:
            new_vectors = np.array(new_vectors, dtype=np.float32)
            self.index.add(new_vectors)
            self.save()
            print(f"[PersistentFAISS] Added {added} new vectors (skipped {len(texts) - added} duplicates)")
        return added

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict]:
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return []
        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        faiss.normalize_L2(query_vector)
        distances, indices = self.index.search(query_vector, k)
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx in self.metadata:
                result = dict(self.metadata[idx])
                result["score"] = float(dist)
                result["id"] = int(idx)
                results.append(result)
        return results

    def save(self):
        if not FAISS_AVAILABLE:
            return
        try:
            faiss.write_index(self.index, str(self.index_file))
            with open(self.meta_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            with open(self.seen_file, 'wb') as f:
                pickle.dump(self.seen_hashes, f)
        except Exception as e:
            print(f"[PersistentFAISS] Save failed: {e}")

    def get_stats(self) -> Dict:
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "unique_hashes": len(self.seen_hashes),
            "dimension": self.dimension,
            "index_file": str(self.index_file),
            "metadata_count": len(self.metadata)
        }

    def clear(self):
        self._create_new()
        for f in [self.index_file, self.meta_file, self.seen_file]:
            if f.exists():
                f.unlink()
        print("[PersistentFAISS] Index cleared")
