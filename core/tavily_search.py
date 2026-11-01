"""
core/tavily_search.py
Tavily AI-optimized web search.
Free tier: 1000 credits/month, no credit card.
"""

import os
import json
from urllib.request import Request, urlopen
from urllib.error import URLError


def tavily_search(
    query: str,
    search_depth: str = "basic",
    max_results: int = 5,
    include_answer: bool = True,
    include_raw_content: bool = False,
    include_images: bool = False,
    topic: str = "general",
    days: int = None,
    api_key: str = None
):
    """
    Tavily AI-optimized web search.

    search_depth: "basic" (1 credit) or "advanced" (2 credits)
    topic: "general", "news", or "finance"
    days: for news topic, how many days back
    """
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        return "[Tavily] No API key found. Set TAVILY_API_KEY in .env"

    try:
        payload = {
            "api_key": key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "include_images": include_images,
            "topic": topic,
        }
        if days and topic == "news":
            payload["days"] = days

        req = Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

            answer = data.get("answer", "")
            results = data.get("results", [])

            formatted = []
            if answer:
                formatted.append(f"**Direct Answer**: {answer}")

            for r in results[:max_results]:
                title = r.get("title", "")
                content = r.get("content", "")
                url = r.get("url", "")
                score = r.get("score", 0)
                formatted.append(f"[{score:.2f}] {title}: {content[:300]}... ({url})")

            return "\n\n".join(formatted) if formatted else "No results found."

    except Exception as e:
        print(f"[Tavily ERROR] {e}")
        return None


def tavily_extract(urls: list, extract_depth: str = "basic", api_key: str = None):
    """
    Extract content from URLs using Tavily.
    Free tier: basic extract included in search credits.
    """
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        return None

    try:
        payload = {
            "api_key": key,
            "urls": urls if isinstance(urls, list) else [urls],
            "extract_depth": extract_depth,
            "include_images": False
        }

        req = Request(
            "https://api.tavily.com/extract",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            return [r.get("raw_content", "") for r in results]

    except Exception as e:
        print(f"[Tavily Extract ERROR] {e}")
        return None