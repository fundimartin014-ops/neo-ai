"""Async SQLite with WAL, single-connection model, serialized writes."""
from __future__ import annotations

import asyncio
import threading
import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    trace_id TEXT,
    user_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_key ON memory_items(key);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    tags TEXT NOT NULL DEFAULT '{}',
    trace_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_metrics_name_ts ON metrics(name, ts DESC);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    schedule TEXT NOT NULL,
    goal TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_run TEXT,
    last_result TEXT,
    next_run TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_next ON scheduled_jobs(enabled, next_run);

CREATE TABLE IF NOT EXISTS market_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    crop TEXT NOT NULL,
    location TEXT NOT NULL,
    raw_text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_crop_ts ON market_history(crop, ts DESC);
"""


class Database:
    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None
        self._lock = threading.Lock()

    async def connect(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        logger.info("db connected: %s", self.path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: tuple = ()) -> None:
        assert self._conn, "Database not connected"
        with self._lock:
            await self._conn.execute(sql, params)
            await self._conn.commit()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        assert self._conn, "Database not connected"
        with self._lock:
            cur = await self._conn.execute(sql, params)
            rows = await cur.fetchall()
            await cur.close()
            return list(rows)

    async def fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        assert self._conn, "Database not connected"
        with self._lock:
            cur = await self._conn.execute(sql, params)
            row = await cur.fetchone()
            await cur.close()
            return row