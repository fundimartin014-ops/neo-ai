# =====================================================================
# core/web_fallback.py
# SECURE WEB FALLBACK AND ANSWERING LAYER
# =====================================================================

import logging
from typing import List
from core.web_search import search_web
from core.memory import remember

logger = logging.getLogger(__name__)


def fetch_web_answers(query: str, max_results: int = 3) -> List[str]:
    """
    Safely queries the web search service and returns a list of text snippets.
    Guaranteed not to crash on string/dictionary type mismatches.
    """
    result = search_web(query, max_results=max_results)
    if not result:
        return []
    
    # Defensive type evaluation
    if isinstance(result, str):
        return [result]
        
    if isinstance(result, dict):
        text = result.get("text") or result.get("msg") or ""
        return [text] if text else []
        
    if isinstance(result, list):
        return [str(item) for item in result if item]
        
    return [str(result)]


class WebAnswerEngine:
    def __init__(self, llm_client=None):
        self.llm = llm_client

    def generate_short_answer(self, question: str, context: str) -> str:
        """
        Fallback answer generator. Uses an attached LLM client if available,
        otherwise returns a clean summary extraction of the text context.
        """
        if self.llm and hasattr(self.llm, 'generate'):
            prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer factually and briefly:"
            return self.llm.generate(prompt)
        
        # Primitive extraction backup if LLM object isn't linked yet
        lines = [line.strip() for line in context.split('\n') if line.strip()]
        return lines[0] if lines else "No clear summary could be generated from context."

    def calculate_confidence(self, context: str) -> int:
        """Calculates a baseline heuristic confidence score based on content density."""
        if not context or len(context) < 50:
            return 10
        if "Source:" in context or "http" in context:
            return 85
        return 60

    def answer(self, text: str):
        """
        Main answering pipeline. Fetches context from the web, calculates 
        confidence profiles, logs data to vector memory, and yields a formatted response.
        """
        result = search_web(text)

        if not result:
            return None

        # Standardizes conflicting structures safely before accessing keys
        if isinstance(result, str):
            logger.warning("[Neo] Received raw string from search provider instead of schema dictionary.")
            raw_text = result
            sources = ["Live Web Stream Fetch"]
        elif isinstance(result, dict):
            raw_text = result.get("text", "No text context found.")
            sources = result.get("sources", [])
        else:
            raw_text = str(result)
            sources = ["Unverified Stream"]

        # Process calculations and generations
        short = self.generate_short_answer(text, raw_text)
        confidence = self.calculate_confidence(raw_text)

        # Build clean citation line strings
        if sources:
            citation_line = "Sources: " + ", ".join(str(s) for s in sources[:3])
        else:
            citation_line = "Sources: Live Search Fetch Pool"

        # Commit to vector memory layers
        try:
            remember(
                input_text=f"[WEB ANSWER] {text}",
                response=short,
                source="web",
                meta={"confidence": confidence}
            )
        except Exception as e:
            logger.error(f"[MEMORY ERROR] Failed logging web query interaction: {e}")

        return (
            f"{short}\n\n"
            f"{citation_line}\n"
            f"Confidence: {confidence}%"
        )