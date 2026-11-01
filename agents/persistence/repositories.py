from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from agents.persistence.db import Database
from agents.schemas import AuditEntry, MemoryItem, Metric


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, entry: AuditEntry) -> int:
        await self.db.execute(
            "INSERT INTO audit_log (ts, event, details, trace_id, user_id) VALUES (?, ?, ?, ?, ?)",
            (
                entry.timestamp.isoformat(),
                entry.event,
                json.dumps(entry.details, default=str),
                entry.trace_id,
                entry.user_id,
            ),
        )
        row = await self.db.fetchone("SELECT last_insert_rowid() AS id")
        return int(row["id"]) if row else -1

    async def recent(self, limit: int = 100, event: str | None = None) -> list[dict[str, Any]]:
        if event:
            rows = await self.db.fetchall(
                "SELECT * FROM audit_log WHERE event = ? ORDER BY id DESC LIMIT ?",
                (event, limit),
            )
        else:
            rows = await self.db.fetchall(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in rows]


class SessionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def upsert(self, session_id: str, data: dict) -> None:
        await self.db.execute(
            "INSERT INTO sessions (session_id, data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            (session_id, json.dumps(data, default=str), _now()),
        )

    async def get(self, session_id: str) -> dict | None:
        row = await self.db.fetchone("SELECT data FROM sessions WHERE session_id = ?", (session_id,))
        return json.loads(row["data"]) if row else None

    async def delete(self, session_id: str) -> None:
        await self.db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    async def all(self) -> dict[str, dict]:
        rows = await self.db.fetchall("SELECT session_id, data FROM sessions")
        return {r["session_id"]: json.loads(r["data"]) for r in rows}


class MemoryRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def store(self, item: MemoryItem) -> int:
        await self.db.execute(
            "INSERT INTO memory_items (key, value, tags, created_at) VALUES (?, ?, ?, ?)",
            (
                item.key,
                json.dumps(item.value, default=str),
                json.dumps(item.tags),
                item.created_at.isoformat(),
            ),
        )
        row = await self.db.fetchone("SELECT last_insert_rowid() AS id")
        return int(row["id"]) if row else -1

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        like = f"%{query}%"
        rows = await self.db.fetchall(
            "SELECT * FROM memory_items WHERE key LIKE ? OR value LIKE ? ORDER BY id DESC LIMIT ?",
            (like, like, limit),
        )
        return [dict(r) for r in rows]

    async def all(self) -> list[dict[str, Any]]:
        rows = await self.db.fetchall("SELECT * FROM memory_items ORDER BY id DESC")
        return [dict(r) for r in rows]


class MetricsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, metric: Metric) -> None:
        await self.db.execute(
            "INSERT INTO metrics (ts, name, value, tags, trace_id) VALUES (?, ?, ?, ?, ?)",
            (
                metric.timestamp.isoformat(),
                metric.name,
                metric.value,
                json.dumps(metric.tags),
                metric.trace_id,
            ),
        )

    async def summary(self) -> list[dict[str, Any]]:
        rows = await self.db.fetchall(
            "SELECT name, COUNT(*) AS count, SUM(value) AS total, AVG(value) AS avg "
            "FROM metrics GROUP BY name"
        )
        return [dict(r) for r in rows]