"""Web search via Tavily. Dedupes by URL, trims whitespace."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from agents.base_agent import BaseAgent


def _norm_url(u: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", (u or "").strip().lower().rstrip("/"))


class SearchAgent(BaseAgent):
    name = "SearchAgent"
    capabilities = ("search",)

    def __init__(self, api_key: str = None, **kw: Any) -> None:
        super().__init__(**kw)
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")

    def _raw_search(self, query: str, max_results: int) -> list[dict]:
        if not self.api_key:
            return [{"error": "TAVILY_API_KEY not set"}]
        body = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": int(max_results),
            "include_answer": False,
        }
        try:
            with httpx.Client(timeout=20) as client:
                r = client.post("https://api.tavily.com/search", json=body)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            return [{"error": f"search failed: {e}"}]
        return data.get("results", []) or []

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        raw = self._raw_search(query, max_results=max_results * 2)
        seen = set()
        out = []
        for item in raw:
            if "error" in item:
                if not out:
                    out.append(item)
                continue
            url = item.get("url", "")
            key = _norm_url(url)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({
                "title": (item.get("title") or "").strip(),
                "url": url.strip(),
                "snippet": (item.get("content") or "").strip()[:600],
            })
            if len(out) >= max_results:
                break
        return out

    def format_for_llm(self, results: list[dict]) -> str:
        lines = []
        for i, r in enumerate(results, 1):
            if "error" in r:
                lines.append(f"[search error] {r['error']}")
                continue
            lines.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
        return "\n\n".join(lines) if lines else "(no results)"

    def run(self, query: str, max_results: int = 5) -> str:
        return self.format_for_llm(self.search(query, max_results=max_results))

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "search":
            q = args[0] if args else ""
            n = int(args[1]) if len(args) > 1 else 5
            return self.run(q, max_results=n)
        if command == "json":
            q = args[0] if args else ""
            n = int(args[1]) if len(args) > 1 else 5
            return json.dumps(self.search(q, max_results=n))
        return f"SearchAgent - command '{command}' not implemented."
