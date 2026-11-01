"""
core/meta_cognition.py
Cloud-first reasoning router with Tavily + OpenRouter free models.
Updated June 2026 verified free model IDs.
"""

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from urllib.request import Request, urlopen
from urllib.error import URLError

from core.tavily_search import tavily_search


class ReasoningTier(Enum):
    FAST = "fast"           # Ollama qwen2.5:1.5b — local, 1.2GB RAM
    STANDARD = "standard"   # Groq llama-3.3-70b — free tier
    DEEP = "deep"           # OpenRouter deepseek-r1:free — reasoning
    CODING = "coding"       # OpenRouter qwen3-235b-a22b:free — code
    LONG = "long"           # OpenRouter llama-4-maverick:free — 1M context
    RESEARCH = "research"   # Tavily + DeepSeek for deep web research


@dataclass
class CritiqueResult:
    accuracy: int
    completeness: int
    helpfulness: int
    missing: str
    query: str
    response: str
    timestamp: str
    model_used: str


class OpenRouterClient:
    """
    Free-tier client. 20 req/min, 200 req/day per model.
    Verified model IDs as of June 2026.
    """

    # CURRENT verified free model IDs (June 2026)
    # Source: openrouter.ai/models filtered by "free"
    FREE_MODELS = {
        "deep": "deepseek/deepseek-r1:free",                    # Reasoning, 64K context
        "coding": "qwen/qwen3-235b-a22b:free",                  # Code, 128K context
        "long": "meta-llama/llama-4-maverick:free",            # 1M context, multimodal
        "general": "meta-llama/llama-3.3-70b-instruct:free",   # General, 131K context
        "fast": "openai/gpt-oss-20b:free",                      # Fast, 131K context
        "chat": "deepseek/deepseek-chat-v3-0324:free",          # Natural conversation
    }

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.available = bool(self.api_key)

    def generate(self, prompt: str, model: str, temperature: float = 0.6, max_tokens: int = 2048) -> Optional[str]:
        if not self.available:
            return None
        try:
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }).encode("utf-8")

            req = Request(
                self.base_url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://neobrain.local",
                    "X-Title": "NeoBrain"
                },
                method="POST"
            )

            with urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"[OpenRouter ERROR] {e}")
            return None


class GroqClient:
    def __init__(self, llm_router):
        self.llm = llm_router

    def generate(self, prompt: str, model: str, temperature: float = 0.4, max_tokens: int = 2048) -> Optional[str]:
        try:
            return self.llm.generate(prompt=prompt, model=model, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:
            print(f"[Groq ERROR] {e}")
            return None


class ReasoningRouter:
    """
    Cloud-first router. Tavily for web research, OpenRouter/Groq for reasoning.
    Updated with June 2026 verified free model IDs.
    """

    MODELS = {
        "fast": {"provider": "ollama", "id": "qwen2.5:1.5b", "temp": 0.3, "max_tokens": 256, "ram_mb": 1200},
        "standard": {"provider": "groq", "id": "llama-3.3-70b-versatile", "temp": 0.4, "max_tokens": 2048},
        "deep": {"provider": "openrouter", "id": "deepseek/deepseek-r1:free", "temp": 0.6, "max_tokens": 4096},
        "coding": {"provider": "openrouter", "id": "qwen/qwen3-235b-a22b:free", "temp": 0.4, "max_tokens": 4096},
        "long": {"provider": "openrouter", "id": "meta-llama/llama-4-maverick:free", "temp": 0.5, "max_tokens": 8192},
        "chat": {"provider": "openrouter", "id": "deepseek/deepseek-chat-v3-0324:free", "temp": 0.7, "max_tokens": 2048},
    }

    RESEARCH_KEYWORDS = [
        "research", "latest news", "current events", "what happened", "recent",
        "today", "this week", "update on", "status of", "price of", "market",
        "news about", "breaking", "headlines", "trending"
    ]

    DEEP_KEYWORDS = [
        "plan", "strategy", "architecture", "design", "optimize", "debug",
        "prove", "calculate", "algorithm", "compare and contrast", "trade-off",
        "evaluate", "critique", "analyze deeply", "step by step", "chain of thought",
        "why does", "how does", "explain the mechanism", "mathematical", "formula",
        "recursive", "complexity", "proof", "theorem", "philosophy", "logic"
    ]

    CODING_KEYWORDS = [
        "code", "function", "class", "debug", "refactor", "implement",
        "algorithm", "python", "javascript", "typescript", "rust", "go",
        "API", "endpoint", "database", "query", "regex", "async", "await",
        "error handling", "exception", "stack trace", "compile", "syntax",
        "docker", "kubernetes", "git", "github", "CI/CD", "ollama"
    ]

    LONG_CONTEXT_KEYWORDS = [
        "document", "pdf", "paper", "book", "chapter", "summarize this",
        "entire", "full text", "long context", "100 pages", "manuscript",
        "contract", "legal document", "research paper", "thesis", "report",
        "analyze this file", "read this", "extract from"
    ]

    FAST_PATTERNS = [
        "hello", "hi", "hey", "what is your name", "how are you",
        "yes", "no", "correct", "wrong", "stop", "start", "ok", "thanks",
        "show context", "clear context", "list goals", "debug", "stats",
        "exit", "quit", "bye"
    ]

    def __init__(self, llm_router):
        self.groq = GroqClient(llm_router)
        self.openrouter = OpenRouterClient()
        self.ollama = llm_router
        self.offline_mode = not (self.groq.llm or self.openrouter.available)

    def classify(self, query: str) -> ReasoningTier:
        q = query.lower().strip()
        if any(q == p or q.startswith(p) for p in self.FAST_PATTERNS):
            return ReasoningTier.FAST
        if any(kw in q for kw in self.RESEARCH_KEYWORDS):
            return ReasoningTier.RESEARCH
        if any(kw in q for kw in self.CODING_KEYWORDS):
            return ReasoningTier.CODING
        if any(kw in q for kw in self.LONG_CONTEXT_KEYWORDS):
            return ReasoningTier.LONG
        if any(kw in q for kw in self.DEEP_KEYWORDS):
            return ReasoningTier.DEEP
        if any(marker in q for marker in ["and then", "first", "finally", "how do i", "steps to", "walk me through"]):
            return ReasoningTier.STANDARD
        return ReasoningTier.STANDARD

    def generate(self, query: str, system_prompt: str = "", context: str = "", force_cloud: bool = False) -> Dict[str, Any]:
        tier = self.classify(query)
        config = self.MODELS.get(tier.value, self.MODELS["standard"])
        if force_cloud and tier == ReasoningTier.FAST:
            tier = ReasoningTier.STANDARD
            config = self.MODELS["standard"]
        if tier == ReasoningTier.RESEARCH:
            return self._research_generate(query, system_prompt, context)
        prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuestion: {query}"
        response = self._try_provider(config, prompt)
        if not response:
            response = self._fallback_chain(prompt, tier)
        reasoning = None
        if tier == ReasoningTier.DEEP and response:
            response, reasoning = self._extract_deepseek_thinking(response)
        return {
            "text": response or "I couldn't generate a response. Please check your connection.",
            "tier": tier.value,
            "model": config["id"],
            "provider": config["provider"],
            "reasoning": reasoning,
            "offline": self.offline_mode
        }

    def _research_generate(self, query: str, system_prompt: str, context: str) -> Dict[str, Any]:
        print(f"[Router] Research mode: Tavily search + DeepSeek synthesis")
        search_results = tavily_search(query, search_depth="basic", max_results=5, include_answer=True)
        if not search_results:
            return self.generate(query, system_prompt, context, force_cloud=True)
        synthesis_prompt = f"""{system_prompt}

You are a research assistant. Synthesize the following search results into a concise, accurate answer.

Search Results:
{search_results}

Question: {query}

Provide a well-structured answer with key facts. Cite sources implicitly."""
        response = self.openrouter.generate(
            prompt=synthesis_prompt,
            model="deepseek/deepseek-r1:free",
            temperature=0.5,
            max_tokens=2048
        )
        return {
            "text": response or search_results[:1000],
            "tier": "research",
            "model": "deepseek/deepseek-r1:free + tavily",
            "provider": "openrouter+tavily",
            "reasoning": None,
            "sources": "tavily"
        }

    def _try_provider(self, config: Dict, prompt: str) -> Optional[str]:
        provider = config["provider"]
        if provider == "ollama":
            return self.ollama.generate(prompt=prompt, model=config["id"], temperature=config["temp"], max_tokens=config["max_tokens"])
        elif provider == "groq":
            return self.groq.generate(prompt=prompt, model=config["id"], temperature=config["temp"], max_tokens=config["max_tokens"])
        elif provider == "openrouter":
            return self.openrouter.generate(prompt=prompt, model=config["id"], temperature=config["temp"], max_tokens=config["max_tokens"])
        return None

    def _fallback_chain(self, prompt: str, original_tier: ReasoningTier) -> Optional[str]:
        print(f"[Router] {original_tier.value} failed, trying fallbacks...")
        fallbacks = [
            ("groq", "llama-3.3-70b-versatile", 0.4),
            ("openrouter", "meta-llama/llama-3.3-70b-instruct:free", 0.4),
            ("openrouter", "deepseek/deepseek-chat-v3-0324:free", 0.7),
        ]
        for provider, model_id, temp in fallbacks:
            try:
                if provider == "groq":
                    r = self.groq.generate(prompt=prompt, model=model_id, temperature=temp, max_tokens=2048)
                else:
                    r = self.openrouter.generate(prompt=prompt, model=model_id, temperature=temp, max_tokens=2048)
                if r:
                    return r
            except Exception:
                continue
        try:
            r = self.ollama.generate(prompt=prompt, model="qwen2.5:1.5b", temperature=0.3, max_tokens=256)
            if r:
                self.offline_mode = True
                return r
        except Exception:
            pass
        return None

    def _extract_deepseek_thinking(self, response: str) -> tuple:
        if "  " in response:
            parts = response.split("  ", 1)
            reasoning = parts[0].replace(" ", "").strip()
            final = parts[1].strip() if len(parts) > 1 else ""
            return final, reasoning
        return response, None


class SelfCritique:
    def __init__(self, llm_router, db_path: str = "brain.db"):
        self.groq = GroqClient(llm_router)
        self.openrouter = OpenRouterClient()
        self.db_path = db_path
        self._init_db()
        self.critique_queue = []
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._background_critique, daemon=True)
        self._worker.start()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS critique_log (id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT, response TEXT, accuracy INTEGER, completeness INTEGER, helpfulness INTEGER, missing TEXT, model_used TEXT, reasoning TEXT, timestamp TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS prompt_evolution (id INTEGER PRIMARY KEY AUTOINCREMENT, pattern TEXT, improved_prompt TEXT, failure_count INTEGER DEFAULT 1, last_seen TEXT)")
        conn.commit()
        conn.close()

    def queue_critique(self, query: str, response: str, model_used: str = "unknown", reasoning: str = None):
        with self._lock:
            self.critique_queue.append({
                "query": query, "response": response,
                "model_used": model_used, "reasoning": reasoning,
                "timestamp": datetime.now().isoformat()
            })

    def _background_critique(self):
        while True:
            time.sleep(5)
            batch = []
            with self._lock:
                if self.critique_queue:
                    batch = self.critique_queue[:3]
                    self.critique_queue = self.critique_queue[3:]
            for item in batch:
                try:
                    self._evaluate(item)
                except Exception as e:
                    print(f"[SelfCritique] Error: {e}")

    def _evaluate(self, item: Dict):
        critique_prompt = f"""Rate this AI response (1-10 each):
1. accuracy - factual correctness
2. completeness - did it answer fully?
3. helpfulness - was it useful?

Query: {item['query']}
Response: {item['response']}

Output STRICT JSON: {{"accuracy": N, "completeness": N, "helpfulness": N, "missing": "..."}}"""
        raw = None
        try:
            raw = self.groq.generate(prompt=critique_prompt, model="llama-3.3-70b-versatile", temperature=0.1, max_tokens=256)
        except Exception:
            pass
        if not raw:
            try:
                raw = self.openrouter.generate(prompt=critique_prompt, model="openai/gpt-oss-20b:free", temperature=0.1, max_tokens=256)
            except Exception:
                return
        if not raw:
            return
        raw = raw.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        try:
            rating = json.loads(raw.strip())
        except json.JSONDecodeError:
            return
        result = CritiqueResult(
            accuracy=rating.get("accuracy", 5),
            completeness=rating.get("completeness", 5),
            helpfulness=rating.get("helpfulness", 5),
            missing=rating.get("missing", ""),
            query=item["query"], response=item["response"],
            timestamp=item["timestamp"], model_used=item["model_used"]
        )
        self._store_critique(result, item.get("reasoning"))
        avg = (result.accuracy + result.completeness + result.helpfulness) / 3
        if avg < 6:
            self._flag_for_improvement(result)

    def _store_critique(self, result: CritiqueResult, reasoning: str = None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO critique_log (query, response, accuracy, completeness, helpfulness, missing, model_used, reasoning, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (result.query, result.response, result.accuracy, result.completeness,
             result.helpfulness, result.missing, result.model_used, reasoning, result.timestamp))
        conn.commit()
        conn.close()

    def _flag_for_improvement(self, result: CritiqueResult):
        pattern = " ".join(result.query.lower().split()[:10])
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT id, failure_count FROM prompt_evolution WHERE pattern = ?", (pattern,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE prompt_evolution SET failure_count = failure_count + 1, last_seen = ? WHERE id = ?",
                      (result.timestamp, row[0]))
        else:
            c.execute("INSERT INTO prompt_evolution (pattern, improved_prompt, last_seen) VALUES (?, ?, ?)",
                      (pattern, f"Address: {result.missing}", result.timestamp))
        conn.commit()
        conn.close()

    def get_failure_patterns(self, min_count: int = 2) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT pattern, failure_count, improved_prompt FROM prompt_evolution WHERE failure_count >= ? ORDER BY failure_count DESC", (min_count,))
        rows = c.fetchall()
        conn.close()
        return [{"pattern": r[0], "count": r[1], "hint": r[2]} for r in rows]

    def get_recent_scores(self, limit: int = 20) -> Dict[str, float]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT AVG(accuracy), AVG(completeness), AVG(helpfulness) FROM critique_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        row = c.fetchone()
        conn.close()
        return {
            "accuracy": round(row[0] or 0, 2),
            "completeness": round(row[1] or 0, 2),
            "helpfulness": round(row[2] or 0, 2)
        }

    def get_reasoning_stats(self, limit: int = 10) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT query, reasoning, model_used, timestamp FROM critique_log WHERE reasoning IS NOT NULL ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"query": r[0], "thinking": r[1], "model": r[2], "time": r[3]} for r in rows]


class UnifiedMemory:
    def __init__(self, embedder, db_path: str = "brain.db"):
        self.embedder = embedder
        self.db_path = db_path

    def store(self, query: str, response: str, source: str = "conversation", meta: Dict = None):
        meta = meta or {}
        try:
            self.embedder.store(query, response)
        except Exception as e:
            print(f"[UnifiedMemory] FAISS error: {e}")
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS unified_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT, response TEXT, source TEXT, meta TEXT, timestamp TEXT)")
            c.execute("INSERT INTO unified_memory (query, response, source, meta, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (query, response, source, json.dumps(meta), datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[UnifiedMemory] SQLite error: {e}")

    def query(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        results = {"semantic": [], "structured": [], "summary": ""}
        try:
            semantic = self.embedder.search(query)
            results["semantic"] = semantic[:top_k]
        except Exception as e:
            print(f"[UnifiedMemory] Semantic error: {e}")
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT query, response, source, timestamp FROM unified_memory WHERE query LIKE ? OR response LIKE ? ORDER BY timestamp DESC LIMIT ?",
                      (f"%{query}%", f"%{query}%", top_k))
            results["structured"] = c.fetchall()
            conn.close()
        except Exception as e:
            print(f"[UnifiedMemory] Structured error: {e}")
        parts = []
        if results["semantic"]:
            parts.append(f"Semantic: {len(results['semantic'])}")
        if results["structured"]:
            parts.append(f"Structured: {len(results['structured'])}")
        results["summary"] = "; ".join(parts) if parts else "No memory"
        return results