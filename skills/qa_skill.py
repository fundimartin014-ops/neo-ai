import logging
import os
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_CHAT = "http://localhost:11434/api/chat"
QA_MODEL = os.getenv("OLLAMA_QA_MODEL", "qwen2.5:1.5b")


class QASkill:
    """
    Hybrid Q&A:
      1. Retrieve from Neo memory (vector store) if available
      2. If memory is empty, fetch Tavily web context
      3. Answer with cloud LLM (Groq → OpenRouter → Ollama)
      4. Fall back to direct Ollama if cloud is exhausted
    """

    def __init__(self):
        pass

    def _retrieve_memory(self, question, top_k=3):
        try:
            from core.memory_bridge import NeoMemory
            mem = NeoMemory(vector_store=None, relational_db=None)
            res = mem.query(question, top_k=top_k)
            if isinstance(res, dict):
                return res.get("summary", "") or ""
        except Exception as e:
            logger.debug(f"qa: memory retrieve skipped: {e}")
        return ""

    def _retrieve_web(self, question, max_results=4):
        try:
            from core.tavily_search import tavily_search
            result = tavily_search(question, search_depth="basic",
                                   max_results=max_results, include_answer=True)
            if isinstance(result, dict):
                return result.get("answer") or "\n".join(
                    r.get("content", "") for r in result.get("results", [])[:max_results]
                )
            return str(result)[:2000]
        except Exception as e:
            logger.debug(f"qa: tavily retrieve skipped: {e}")
        return ""

    def _llm_answer(self, question, context):
        system = (
            "You are Neo. Answer concisely and factually. "
            "If CONTEXT is provided, ground your answer in it. "
            "If CONTEXT is empty, answer from your knowledge."
        )
        user = f"CONTEXT:\n{context}\n\nQUESTION:\n{question}" if context else question

        # Tier 1: cloud via LocalLLM
        try:
            from core.local_llm import LocalLLM
            llm = LocalLLM()
            answer = llm.generate(user, system=system, temperature=0.3, max_tokens=768)
            if answer and len(answer) > 3 and not answer.startswith("[Neo]"):
                return answer
        except Exception as e:
            logger.warning(f"qa: LocalLLM failed: {e}")

        # Tier 2: direct Ollama
        try:
            r = requests.post(
                OLLAMA_CHAT,
                json={
                    "model": QA_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 512},
                },
                timeout=90,
            )
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            return f"[Error] No LLM available: {e}"

    def process(self, inputs: dict) -> dict:
        question = str(inputs.get("question", "")).strip()
        if not question:
            return {"error": "question is required"}

        logger.info(f"QASkill: {question[:80]}")
        context_parts = []
        mem_ctx = self._retrieve_memory(question)
        if mem_ctx:
            context_parts.append(f"[Memory]\n{mem_ctx}")
        web_ctx = self._retrieve_web(question)
        if web_ctx:
            context_parts.append(f"[Web]\n{web_ctx}")

        context = "\n\n".join(context_parts)
        answer = self._llm_answer(question, context)
        return {
            "answer": answer,
            "context_used": bool(context),
            "memory_used": bool(mem_ctx),
            "web_used": bool(web_ctx),
        }