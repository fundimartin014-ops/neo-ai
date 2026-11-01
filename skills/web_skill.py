import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handle(query):
    """
    Hybrid web lookup:
      1. Tavily (fast, high-quality)
      2. DuckDuckGo fallback
    """
    if not query:
        return None

    try:
        from core.tavily_search import tavily_search
        result = tavily_search(query, search_depth="basic", max_results=5, include_answer=True)
        if isinstance(result, dict):
            answer = result.get("answer")
            if answer:
                return answer
            results = result.get("results", [])
            if results:
                return "\n".join(
                    f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
                    for r in results[:5]
                )
        return str(result)[:1500]
    except Exception as e:
        logger.debug(f"web: tavily failed: {e}")

    # DuckDuckGo fallback
    try:
        from core.web_search import search_web
        result = search_web(query)
        return str(result)[:1500] if result else None
    except Exception as e:
        logger.debug(f"web: ddg failed: {e}")

    return None