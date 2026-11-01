# =====================================================================
# core/unified_search.py
# HARDENED UNIFIED SEARCH ORCHESTRATOR AND ROUTER
# =====================================================================

import os
import json
import logging
import requests
from typing import Dict, Any
from core.web_search import search_web, UnbreakableSearchPayload, DictStr

logger = logging.getLogger(__name__)


def search_serper(query: str) -> Any:
    """
    Direct interface worker for the Serper (Google) API instance.
    """
    serper_key = os.environ.get("SERPER_API_KEY")
    if not serper_key:
        return "Serper Engine Error: MISSING_KEY"
    
    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": serper_key,
            "Content-Type": "application/json"
        }
        payload = {"q": query}
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"[Serper] API responded with error code: {response.status_code}")
            return f"Serper Engine Error HTTP {response.status_code}"
            
        return response.json()

    except Exception as e:
        logger.error(f"[Serper Worker Exception] {e}")
        return f"Serper connection failure: {e}"


def unified_search(query: str) -> Any:
    """
    Sweeps all active search infrastructure profiles, dynamically ranks them,
    and returns a standardized payload compatible with any dict or list interaction pattern.
    Guaranteed never to leak raw unformatted string diagnostics to downstream engines.
    """
    logger.info(f"🚀 [UnifiedSearch] Sweeping all search pools for: '{query}'")
    
    raw_result = None
    source_label = "None Selected"

    # 1. Evaluate Tier 1 Source: Serper (Google API Router)
    if os.environ.get("SERPER_API_KEY"):
        try:
            raw_result = search_serper(query)
            source_label = "Success via Serper (Google) (Quality Tier 2)"
        except Exception as e:
            logger.error(f"[UnifiedSearch] High tier search sweep missed: {e}")
            raw_result = None

    # Verify if structural content was actually gathered by Tier 1
    has_valid_content = False
    if raw_result and isinstance(raw_result, dict):
        if "organic" in raw_result and raw_result.get("organic"):
            has_valid_content = True
        elif "text" in raw_result and raw_result.get("text"):
            has_valid_content = True
    elif raw_result and isinstance(raw_result, str):
        # Only treat string as valid if it isn't an explicit warning signature
        if len(raw_result.strip()) > 30 and "Error" not in raw_result and "failure" not in raw_result:
            has_valid_content = True

    # 2. Evaluate Tier 2 Fallback Source: Local DuckDuckGo Scraper Integration
    if not has_valid_content:
        try:
            logger.info("[UnifiedSearch] Tier 1 empty or invalid. Re-routing search queries to DuckDuckGo Scraper Core...")
            web_payload = search_web(query)
            logger.info("👑 [UnifiedSearch] Best Source Selected: Success via DuckDuckGo Scraper (Quality Tier 3)")
            return web_payload
        except Exception as e:
            logger.critical(f"[UnifiedSearch] Critical Fallback Layer collapse: {e}")
            return UnbreakableSearchPayload(
                {"text": "All integrated remote search protocols failed completely.", "sources": []},
                []
            )

    logger.info(f"👑 [UnifiedSearch] Best Source Selected: {source_label}")

    # =====================================================================
    # 🛡️ THE TYPE SHIELD LAYER (CRASH PREVENTION HOOK)
    # =====================================================================
    try:
        # Case A: String object returned by Serper layer
        if isinstance(raw_result, str):
            try:
                parsed_json = json.loads(raw_result)
                if isinstance(parsed_json, dict):
                    raw_result = parsed_json
            except json.JSONDecodeError:
                smart_diagnostic = f"Search reference text: {raw_result}"
                return UnbreakableSearchPayload(
                    {"text": smart_diagnostic, "sources": []},
                    [{"text": smart_diagnostic, "snippet": smart_diagnostic, "url": "", "link": "", "title": "Diagnostic Data", "sources": []}]
                )

        # Case B: System engine processed a verified Python dictionary
        if isinstance(raw_result, dict):
            if "organic" in raw_result:
                organic_items = raw_result.get("organic", [])
                snippets = []
                links = []
                data_list = []
                
                for item in organic_items:
                    if not isinstance(item, dict):
                        continue
                    snippet = item.get("snippet", "")
                    link = item.get("link", "")
                    title = item.get("title", "Google Search Entry")
                    
                    if snippet:
                        snippets.append(snippet)
                    if link:
                        smart_link = DictStr(link)
                        links.append(smart_link)
                        
                        data_list.append({
                            "text": snippet,
                            "snippet": snippet,
                            "url": smart_link,
                            "link": smart_link,
                            "title": title,
                            "sources": [smart_link]
                        })
                
                combined_text = " ".join(snippets) if snippets else "No context snippets returned."
                return UnbreakableSearchPayload(
                    {"text": combined_text, "sources": links},
                    data_list
                )
            else:
                text_content = str(raw_result.get("text") or raw_result.get("msg") or "Empty payload field structure.")
                sources_list = raw_result.get("sources") or []
                wrapped_sources = [DictStr(s) for s in sources_list if isinstance(s, str)]
                
                return UnbreakableSearchPayload(
                    {"text": text_content, "sources": wrapped_sources},
                    [{"text": text_content, "snippet": text_content, "url": "", "link": "", "title": "General Context Hit", "sources": wrapped_sources}]
                )

    except Exception as type_guard_exception:
        logger.error(f"[Type Shield Crash Intercepted] Normalizing crash state: {type_guard_exception}")
        
    # Catch-all fallback default object container
    return UnbreakableSearchPayload(
        {"text": "Context extraction processing structural failure.", "sources": []},
        []
    )