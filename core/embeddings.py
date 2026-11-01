# core/embeddings.py
from sentence_transformers import SentenceTransformer, CrossEncoder

class EmbeddingEngine:
    def __init__(self, model_name="BAAI/bge-large-en-v1.5"):
        self.encoder = SentenceTransformer(model_name)
        self.reranker = CrossEncoder("BAAI/bge-reranker-base")
        
    def encode(self, texts: List[str]) -> np.ndarray:
        # BGE models prefer instructions
        instruction = "Represent this sentence for searching relevant passages: "
        texts = [instruction + t for t in texts]
        return self.encoder.encode(texts, normalize_embeddings=True)
        
    def rerank(self, query: str, passages: List[str], top_k: int = 5) -> List[Dict]:
        """Two-stage retrieval: semantic search + rerank"""
        pairs = [[query, p] for p in passages]
        scores = self.reranker.predict(pairs)
        
        ranked = sorted(zip(passages, scores), key=lambda x: x[1], reverse=True)
        return [{"text": p, "score": float(s)} for p, s in ranked[:top_k]]