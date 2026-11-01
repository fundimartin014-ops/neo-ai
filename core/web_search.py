# ============================================
# core/web_search.py
# SERPER + SERPAPI + DDGS FALLBACK
# ============================================

import re
import os
import logging
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from core.memory import remember, search_knowledge

logger = logging.getLogger(__name__)

# ============================================
# KEY RESOLUTION
# ============================================

def _get_serper_key():
    return os.getenv("SERPER_API_KEY") or os.getenv("WEB_SEARCH_API_KEY")

def _get_serpapi_key():
    return os.getenv("SERPAPI_API_KEY")

def _has_serper():
    return bool(_get_serper_key())

def _has_serpapi():
    return bool(_get_serpapi_key())

# ============================================
# CACHE
# ============================================

def check_cache(query):
    try:
        cached = search_knowledge(f"[WEB_CACHE] {query}")
        if cached and len(cached) > 0:
            item = cached[0]
            if isinstance(item, dict):
                return item.get("response")
    except Exception as e:
        logger.error(f"[CACHE ERROR] {e}")
    return None

def save_cache(query, content):
    try:
        remember(
            input_text=f"[WEB_CACHE] {query}",
            response=content,
            source="web_cache"
        )
    except Exception as e:
        logger.error(f"[CACHE SAVE ERROR] {e}")

# ============================================
# TEXT CLEANING
# ============================================

def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    return text.strip()

def extract_text(url, max_chars=3000):
    try:
        if not url or "youtube.com" in url.lower():
            return None
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Encoding": "gzip, deflate"
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "svg", "nav", "aside"]):
            tag.decompose()
        text = clean_text(soup.get_text(" "))
        return text[:max_chars] if len(text) > 100 else None
    except Exception as e:
        logger.debug(f"[SCRAPE ERROR] {url}: {e}")
        return None

def summarize(query, text):
    query_words = query.lower().split()
    sentences = re.split(r'(?<=[.!?]) +', text)
    scored = []
    for sentence in sentences:
        s = sentence.strip()
        if len(s) < 40:
            continue
        score = sum(1 for word in query_words if word in s.lower())
        if score > 0:
            scored.append((score, s))
    scored.sort(reverse=True, key=lambda x: x[0])
    best = [x[1] for x in scored[:5]]
    return " ".join(best) if best else text[:500]

# ============================================
# SEARCH PROVIDERS
# ============================================

def _search_serper(query, max_results=3):
    key = _get_serper_key()
    if not key:
        return None
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=15
        )
        r.raise_for_status()
        data = r.json()
        combined = ""
        sources = []
        for item in data.get("organic", [])[:max_results]:
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            sources.append(link)
            combined += f"\n\nSource: {link}\n{title}\n{snippet}"
        if not combined:
            return None
        summary = summarize(query, combined)
        return {"text": summary, "sources": sources, "provider": "serper"}
    except Exception as e:
        logger.warning(f"[Serper Error] {e}")
        return None

def _search_serpapi(query, max_results=3):
    key = _get_serpapi_key()
    if not key:
        return None
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": query, "api_key": key, "num": max_results},
            timeout=15
        )
        r.raise_for_status()
        data = r.json()
        combined = ""
        sources = []
        for item in data.get("organic_results", [])[:max_results]:
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            sources.append(link)
            combined += f"\n\nSource: {link}\n{title}\n{snippet}"
        if not combined:
            return None
        summary = summarize(query, combined)
        return {"text": summary, "sources": sources, "provider": "serpapi"}
    except Exception as e:
        logger.warning(f"[SerpAPI Error] {e}")
        return None

def _search_ddgs(query, max_results=3):
    try:
        combined = ""
        sources = []
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        blocked = ["youtube.com", "facebook.com", "x.com", "twitter.com", "instagram.com"]
        for r in results:
            if not isinstance(r, dict):
                continue
            url = r.get("href")
            if not url or any(b in url.lower() for b in blocked):
                continue
            page = extract_text(url)
            text_content = page if page else r.get("body", "")
            if text_content:
                combined += f"\n\nSource: {url}\n{text_content}"
                sources.append(url)
        if not combined:
            return None
        summary = summarize(query, combined)
        return {"text": summary, "sources": sources, "provider": "ddgs"}
    except Exception as e:
        logger.warning(f"[DDGS Error] {e}")
        return None

# ============================================
# MAIN ENTRYPOINT
# ============================================

def search_web(query, max_results=3):
    cached = check_cache(query)
    if cached:
        logger.info("⚡ Using cached web result")
        return {"text": cached, "sources": [], "provider": "cache"}

    if _has_serper():
        logger.info(f"🔎 Searching via Serper: '{query}'")
        result = _search_serper(query, max_results)
        if result:
            save_cache(query, result["text"])
            return result

    if _has_serpapi():
        logger.info(f"🔎 Searching via SerpAPI: '{query}'")
        result = _search_serpapi(query, max_results)
        if result:
            save_cache(query, result["text"])
            return result

    logger.info(f"🌍 Searching via DDGS (free fallback): '{query}'")
    result = _search_ddgs(query, max_results)
    if result:
        save_cache(query, result["text"])
        return result

    logger.error("[WEB SEARCH] All providers failed.")
    return {"text": "No web results available.", "sources": [], "provider": "none"}