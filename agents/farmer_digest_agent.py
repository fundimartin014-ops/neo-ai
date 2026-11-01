"""FarmerDigestAgent — daily brief with weather, market trends, pest alerts, irrigation advice."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from agents.base_agent import BaseAgent
from agents.llm import get_llm
from agents.locations import resolve_location, known_towns


FARM_BRIEF_SYSTEM = """You are an agricultural advisor producing a daily brief for a smallholder farmer.

Input sections provided by an automated system:
  WEATHER      — 3-day forecast for the location
  MARKET_NOW   — today's market search results
  MARKET_PREV  — the most recent previous snapshot (may be empty on first run)
  PESTS        — recent pest/disease outbreak news for the region
  IRRIGATION   — computed advisory from the rainfall rule

Produce a markdown brief with exactly this structure:

## Today's Farmer Brief — {date}
Location: {location}

### Weather
Two sentences on temperature range and rain likelihood; mention field-work impact.

### Market Watch
2-3 bullets. For each crop, compare MARKET_NOW vs MARKET_PREV. If MARKET_PREV exists,
say whether the price is up/down/flat with a rough percentage. If no prior data,
just state the current price.

### Pest & Disease Alerts
If PESTS mentions active outbreaks, 1-2 bullets naming the pest and the affected crop.
If nothing relevant, say "No active regional alerts today."

### Irrigation
State the IRRIGATION advice verbatim if non-empty. Otherwise say "Soil moisture
outlook normal — no irrigation action needed."

### Action Items
1-3 short, concrete steps the farmer can act on today, informed by all sections above.

Keep under 450 words. No preamble. No closing remarks."""


class FarmerDigestAgent(BaseAgent):
    name = "FarmerDigestAgent"
    capabilities = ("farm_brief",)

    def __init__(self, llm=None, registry=None, **kw: Any) -> None:
        super().__init__(**kw)
        self.registry = registry
        try:
            self.llm = llm or get_llm()
        except Exception:
            self.llm = None

    # ---------------------------------------------------------------- weather
    def _weather_raw(self, lat: float, lon: float) -> dict:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
            "&timezone=Africa%2FNairobi&forecast_days=3"
        )
        try:
            with httpx.Client(timeout=15) as c:
                r = c.get(url)
                r.raise_for_status()
                return r.json().get("daily", {}) or {}
        except Exception as e:
            return {"_error": str(e)}

    def _format_weather(self, d: dict) -> str:
        if "_error" in d:
            return f"[weather error] {d['_error']}"
        times = d.get("time") or []
        tmaxs = d.get("temperature_2m_max") or []
        tmins = d.get("temperature_2m_min") or []
        precs = d.get("precipitation_sum") or []
        lines = []
        for i, day in enumerate(times[:3]):
            tmax = tmaxs[i] if i < len(tmaxs) else "?"
            tmin = tmins[i] if i < len(tmins) else "?"
            prec = precs[i] if i < len(precs) else "?"
            lines.append(f"{day}: {tmin}-{tmax}C, rain {prec}mm")
        return "\n".join(lines) if lines else "(no weather data)"

    def _irrigation_advice(self, d: dict) -> str:
        """Sum the 3-day precipitation. If dry, recommend irrigating."""
        if "_error" in d:
            return ""
        precs = [p for p in (d.get("precipitation_sum") or []) if isinstance(p, (int, float))]
        if not precs:
            return ""
        total = sum(precs[:3])
        if total < 5.0:
            return (f"Only {total:.1f}mm rain forecast over the next 3 days. "
                    f"Irrigate tomorrow morning.")
        if total > 40.0:
            return (f"Heavy rain forecast ({total:.1f}mm over 3 days). "
                    f"Delay irrigation and check field drainage.")
        return ""

    # ------------------------------------------------------------- market
    def _market_search(self, crops: str, location: str) -> str:
        from agents.search_agent import SearchAgent
        s = SearchAgent()
        return s.run(f"{crops} market price {location} today Kenya shillings", max_results=3)

    async def _market_previous(self, crops: str, location: str) -> str:
        """Look up the last non-today snapshot for this crop set."""
        reg = getattr(self, "registry", None)
        if reg is None:
            return ""
        market_agent = reg.get("MarketAgent")
        if market_agent is None:
            return ""
        try:
            return await market_agent.previous_for(crops, location) or ""
        except Exception as e:
            self.logger.warning("market previous lookup failed: %s", e)
            return ""

    async def _market_store(self, crops: str, location: str, raw_text: str) -> None:
        reg = getattr(self, "registry", None)
        if reg is None:
            return
        market_agent = reg.get("MarketAgent")
        if market_agent is None:
            return
        try:
            await market_agent.record(crops, location, raw_text)
        except Exception as e:
            self.logger.warning("market record failed: %s", e)

    # -------------------------------------------------------------- pest
    def _pest_alerts(self, location: str) -> str:
        from agents.search_agent import SearchAgent
        s = SearchAgent()
        return s.run(f"pest disease outbreak {location} Kenya farming 2026", max_results=3)

    # ------------------------------------------------------------- compose
    async def compose_brief(
        self,
        location: str = "Nakuru",
        latitude: float = None,
        longitude: float = None,
        crops: str = "maize milk beans",
        topic: str = "agriculture",
    ) -> str:
        # Resolve location -> coordinates if not supplied
        if latitude is None or longitude is None:
            hit = resolve_location(location)
            if hit is not None:
                latitude, longitude, location = hit
            else:
                latitude = latitude if latitude is not None else -0.3031
                longitude = longitude if longitude is not None else 36.0800
        weather_raw = self._weather_raw(latitude, longitude)
        weather_txt = self._format_weather(weather_raw)
        irrigation = self._irrigation_advice(weather_raw)

        market_now = self._market_search(crops, location)
        market_prev = await self._market_previous(crops, location)
        await self._market_store(crops, location, market_now)

        pests = self._pest_alerts(location)

        if not self.llm:
            return (
                f"## Farmer Brief — {datetime.now().strftime('%Y-%m-%d')}\n"
                f"Location: {location}\n\n"
                f"### Weather\n{weather_txt}\n\n"
                f"### Irrigation\n{irrigation or '(normal)'}\n\n"
                f"### Market (today)\n{market_now}\n\n"
                f"### Market (previous)\n{market_prev or '(none)'}\n\n"
                f"### Pests\n{pests}"
            )

        user_input = (
            f"DATE: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"LOCATION: {location}\n\n"
            f"=== WEATHER ===\n{weather_txt}\n\n"
            f"=== MARKET_NOW ===\n{market_now}\n\n"
            f"=== MARKET_PREV ===\n{market_prev or '(none)'}\n\n"
            f"=== PESTS ===\n{pests}\n\n"
            f"=== IRRIGATION ===\n{irrigation or '(none)'}\n"
        )
        try:
            return await self.llm.chat(
                [{"role": "system", "content": FARM_BRIEF_SYSTEM},
                 {"role": "user", "content": user_input}],
                temperature=0.4,
            )
        except Exception as e:
            return f"[brief error] {e}\n\nRaw:\n\n{user_input}"

    async def arun(self, location: str = "Nakuru",
                   latitude: float = -0.3031, longitude: float = 36.0800,
                   crops: str = "maize milk beans", topic: str = "agriculture") -> str:
        return await self.compose_brief(location, latitude, longitude, crops, topic)

    def run(self, location: str = "Nakuru",
            latitude: float = -0.3031, longitude: float = 36.0800,
            crops: str = "maize milk beans", topic: str = "agriculture") -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.compose_brief(
                        location, latitude, longitude, crops, topic)).result()
            return loop.run_until_complete(self.compose_brief(
                location, latitude, longitude, crops, topic))
        except RuntimeError:
            return asyncio.run(self.compose_brief(
                location, latitude, longitude, crops, topic))

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "brief":
            loc = args[0] if args else "Nakuru"
            return self.run(location=loc)
        return f"FarmerDigestAgent - command '{command}' not implemented."
