"""
core/memory_bridge.py
Unified memory interface: vector + relational + episodic.
Single query point for the orchestrator.
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime


class NeoMemory:
    def __init__(self, vector_store=None, relational_db=None,
                 embedding_engine=None, max_history: int = 20):
        self.vector = vector_store
        self.relational = relational_db
        self.embedder = embedding_engine
        self.episodic: List[Dict] = []
        self.max_history = max_history
        self.fact_cache: Dict[str, str] = {}

    def query(self, text: str, top_k: int = 5, include_history: bool = True) -> Dict:
        results = {"semantic": [], "factual": [], "recent_context": [], "summary": ""}

        if self.vector and self.embedder:
            try:
                query_vec = self.embedder.encode([text])
                vector_results = self.vector.search(query_vec, k=top_k * 2)
                if hasattr(self.embedder, 'rerank'):
                    passages = [r["text"] for r in vector_results]
                    vector_results = self.embedder.rerank(text, passages, top_k=top_k)
                else:
                    vector_results = vector_results[:top_k]
                results["semantic"] = vector_results
            except Exception as e:
                print(f"[NeoMemory] Vector search error: {e}")

        if self.relational:
            try:
                factual_results = self._query_relational(text)
                results["factual"] = factual_results
            except Exception as e:
                print(f"[NeoMemory] Relational search error: {e}")

        if include_history:
            results["recent_context"] = self._get_relevant_history(text)

        results["summary"] = self._build_summary(results)
        return results

    def _query_relational(self, text: str) -> List[Dict]:
        if not self.relational:
            return []
        try:
            from core.memory import search_memory
            facts = search_memory(text, limit=5)
            return [{"fact": f, "source": "brain.db"} for f in facts]
        except ImportError:
            pass
        try:
            import sqlite3
            conn = sqlite3.connect("brain.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT input_text, response, source, meta FROM memory
                WHERE input_text LIKE ? OR response LIKE ?
                ORDER BY rowid DESC LIMIT 5
            """, (f"%{text}%", f"%{text}%"))
            rows = cursor.fetchall()
            conn.close()
            return [
                {"input": row[0], "response": row[1], "source": row[2] or "brain.db",
                 "meta": json.loads(row[3]) if row[3] else {}}
                for row in rows
            ]
        except Exception as e:
            print(f"[NeoMemory] SQLite fallback error: {e}")
            return []

    def _get_relevant_history(self, text: str, max_turns: int = 5) -> List[Dict]:
        return self.episodic[-max_turns:] if self.episodic else []

    def _build_summary(self, results: Dict) -> str:
        parts = []
        if results["semantic"]:
            texts = [f"- {r.get('text', r.get('fact', ''))[:300]}..."
                     for r in results["semantic"][:3]]
            parts.append("From documents:\n" + "\n".join(texts))
        if results["factual"]:
            facts = [f"- {r.get('response', r.get('fact', ''))[:200]}"
                     for r in results["factual"][:3]]
            parts.append("From knowledge base:\n" + "\n".join(facts))
        if results["recent_context"]:
            recent = []
            for turn in results["recent_context"][-3:]:
                recent.append(f"User: {turn.get('user', '')[:100]}")
                recent.append(f"Neo: {turn.get('assistant', '')[:100]}")
            parts.append("Recent conversation:\n" + "\n".join(recent))
        return "\n\n".join(parts) if parts else "No relevant memory found."

    def remember_exchange(self, user_msg: str, assistant_msg: str,
                          tools_used: Optional[List[str]] = None, mode: str = "unknown"):
        self.episodic.append({
            "user": user_msg, "assistant": assistant_msg,
            "tools": tools_used or [], "mode": mode,
            "timestamp": datetime.now().isoformat()
        })
        if len(self.episodic) > self.max_history:
            self.episodic = self.episodic[-self.max_history:]

    def add_fact(self, fact: str, category: str = "general", source: str = "user"):
        try:
            from core.memory import remember
            remember(input_text=f"fact:{category}", response=fact,
                     source=source, meta={"category": category, "auto": True})
        except ImportError:
            print(f"[NeoMemory] Cannot store fact: core.memory.remember not available")

    def get_stats(self) -> Dict:
        return {
            "episodic_turns": len(self.episodic),
            "vector_entries": self.vector.get_stats() if self.vector else {},
            "has_relational": self.relational is not None,
            "has_embedder": self.embedder is not None
        }
