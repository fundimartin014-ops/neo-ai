from pathlib import Path

content = '''"""LocationAgent — reverse-geocode coordinates to a place name, and lookup coords by name.

Backend: HERE Maps (free tier 250K req/month).
Env: HERE_API_KEY
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from agents.base_agent import BaseAgent


class LocationAgent(BaseAgent):
    name = "LocationAgent"
    capabilities = ("location",)

    REVERSE_URL = "https://revgeocode.search.hereapi.com/v1/revgeocode"
    FORWARD_URL = "https://geocode.search.hereapi.com/v1/geocode"

    def _key(self) -> str:
        return os.getenv("HERE_API_KEY", "").strip()

    def reverse(self, latitude: float, longitude: float) -> dict:
        key = self._key()
        if not key:
            return {"error": "HERE_API_KEY not set in .env"}
        try:
            with httpx.Client(timeout=15) as c:
                r = c.get(
                    self.REVERSE_URL,
                    params={
                        "at": f"{latitude},{longitude}",
                        "lang": "en",
                        "apiKey": key,
                    },
                )
                if r.status_code != 200:
                    return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
                data = r.json()
        except Exception as e:
            return {"error": f"request failed: {e}"}

        items = data.get("items", [])
        if not items:
            return {"error": "no match for coordinates"}
        top = items[0]
        addr = top.get("address", {}) or {}
        return {
            "error": None,
            "city": addr.get("city") or addr.get("county") or addr.get("state") or "",
            "county": addr.get("county", ""),
            "state": addr.get("state", ""),
            "country": addr.get("countryName", ""),
            "label": addr.get("label", ""),
            "latitude": latitude,
            "longitude": longitude,
        }

    def forward(self, place: str) -> dict:
        key = self._key()
        if not key:
            return {"error": "HERE_API_KEY not set in .env"}
        try:
            with httpx.Client(timeout=15) as c:
                r = c.get(
                    self.FORWARD_URL,
                    params={"q": place, "in": "countryCode:KEN", "apiKey": key},
                )
                if r.status_code != 200:
                    return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
                data = r.json()
        except Exception as e:
            return {"error": f"request failed: {e}"}

        items = data.get("items", [])
        if not items:
            return {"error": f"no match for {place!r}"}
        top = items[0]
        pos = top.get("position", {}) or {}
        addr = top.get("address", {}) or {}
        return {
            "error": None,
            "city": addr.get("city") or place,
            "label": addr.get("label", ""),
            "latitude": pos.get("lat"),
            "longitude": pos.get("lng"),
        }

    def run(self, query: str = "") -> str:
        # "reverse:LAT,LON" or a place name
        q = (query or "").strip()
        if not q:
            return "LocationAgent: use 'reverse:lat,lon' or a place name."
        if q.lower().startswith("reverse:"):
            try:
                coords = q.split(":", 1)[1].split(",")
                lat, lon = float(coords[0]), float(coords[1])
            except Exception as e:
                return f"[location error] bad coords: {e}"
            r = self.reverse(lat, lon)
            if r.get("error"):
                return f"[location error] {r['error']}"
            return f"{r['city']}, {r['county']}, {r['country']}  ({r['latitude']}, {r['longitude']})"
        else:
            r = self.forward(q)
            if r.get("error"):
                return f"[location error] {r['error']}"
            return f"{r['city']}  ({r['latitude']}, {r['longitude']})"

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "reverse" and len(args) >= 2:
            r = self.reverse(float(args[0]), float(args[1]))
            if r.get("error"):
                return f"[location error] {r['error']}"
            return r.get("city", "")
        if command == "forward" and args:
            r = self.forward(args[0])
            if r.get("error"):
                return f"[location error] {r['error']}"
            return f"{r['latitude']},{r['longitude']}"
        return f"LocationAgent - command '{command}' not implemented."
'''

Path("agents/location_agent.py").write_text(content, encoding="utf-8")
print("Created agents/location_agent.py")