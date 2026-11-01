"""MarketAgent — stores daily price snapshots and returns prior context for trend analysis."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from agents.base_agent import BaseAgent
from agents.persistence import Database


class MarketAgent(BaseAgent):
    name = "MarketAgent"
    capabilities = ("market",)

    def __init__(self, db: Database, **kw: Any) -> None:
        super().__init__(**kw)
        self.db = db

    # ------------------------------------------------------------------ store
    async def record(self, crop: str, location: str, raw_text: str) -> str:
        await self.db.execute(
            "INSERT INTO market_history (ts, crop, location, raw_text) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), crop.strip().lower(),
             location.strip().lower(), raw_text[:4000]),
        )
        return f"Recorded market snapshot for {crop}"

    # -------------------------------------------------------------- previous
    async def previous_for(self, crop: str, location: str, days_back: int = 10) -> str:
        """Return the most recent PRIOR snapshot's raw text (before today)."""
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        today_start = datetime.now().replace(hour=0, minute=0, second=0,
                                             microsecond=0).isoformat()
        row = await self.db.fetchone(
            "SELECT ts, raw_text FROM market_history "
            "WHERE crop = ? AND location = ? AND ts >= ? AND ts < ? "
            "ORDER BY ts DESC LIMIT 1",
            (crop.strip().lower(), location.strip().lower(), cutoff, today_start),
        )
        if not row:
            return ""
        return f"(from {row['ts'][:10]})\n{row['raw_text']}"

    async def history(self, crop: str, limit: int = 7) -> list[dict]:
        rows = await self.db.fetchall(
            "SELECT ts, raw_text FROM market_history WHERE crop = ? "
            "ORDER BY ts DESC LIMIT ?",
            (crop.strip().lower(), int(limit)),
        )
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- command
    async def ahandle_command(self, command: str, *args: Any) -> str:
        if command == "record":
            return await self.record(args[0], args[1], args[2])
        if command == "previous":
            return await self.previous_for(args[0], args[1]) or "(none)"
        if command == "history":
            items = await self.history(args[0])
            if not items:
                return "(no history)"
            return "\n\n".join(f"{i['ts'][:16]} — {i['raw_text'][:140]}" for i in items)
        return f"MarketAgent - command '{command}' not implemented."


    async def arun(self, crop_query: str = "") -> str:
        """Turn a plain 'maize milk beans' payload into a price search."""
        from agents.search_agent import SearchAgent
        s = SearchAgent()
        return s.run(f"{crop_query or self.name} market price Kenya today", max_results=3)

    def run(self, crop_query: str = "") -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.arun(crop_query)).result()
            return loop.run_until_complete(self.arun(crop_query))
        except RuntimeError:
            return asyncio.run(self.arun(crop_query))

    def handle_command(self, command: str, *args: Any) -> str:
        import asyncio
        return asyncio.run(self.ahandle_command(command, *args))
