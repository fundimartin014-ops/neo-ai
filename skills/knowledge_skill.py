import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handle(query):
    """
    Hybrid knowledge lookup:
      1. Neo semantic memory
      2. Tavily web search fallback
    Returns a plain string (handle-style skills return strings).
    """
    if not query:
        return None

    # Try semantic memory
    try:
        from core.semantic_memory import search
        results = search(query)
        if results:
            top = results[0]
            if isinstance(top, dict):
                return top.get("response") or top.get("text") or str(top)
            return str(top)
    except Exception as e:
        logger.debug(f"knowledge: memory failed: {e}")

    # Try Tavily
    try:
        from core.tavily_search import tavily_search
        result = tavily_search(query, search_depth="basic", max_results=3, include_answer=True)
        if isinstance(result, dict):
            return result.get("answer") or (result.get("results", [{}])[0].get("content") if result.get("results") else None)
        return str(result)[:1500]
    except Exception as e:
        logger.debug(f"knowledge: tavily failed: {e}")

    return None