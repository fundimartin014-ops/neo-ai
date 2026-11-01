"""Lightweight forward-only migrations. No Alembic dependency, but same idea."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from agents.persistence.db import Database

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    version: int
    description: str
    sql: str


MIGRATIONS: list[Migration] = [
    Migration(1, "initial_schema", ""),  # schema itself lives in db.SCHEMA (baseline)
    Migration(2, "add_audit_severity", """
        ALTER TABLE audit_log ADD COLUMN severity TEXT DEFAULT 'info';
        CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log(severity);
    """),
    Migration(3, "add_memory_embeddings", """
        CREATE TABLE IF NOT EXISTS memory_embeddings (
            memory_id INTEGER PRIMARY KEY,
            vector BLOB NOT NULL,
            dim INTEGER NOT NULL,
            model TEXT NOT NULL,
            FOREIGN KEY (memory_id) REFERENCES memory_items(id) ON DELETE CASCADE
        );
    """),
    Migration(4, "add_rate_limit_counters", """
        CREATE TABLE IF NOT EXISTS rate_limit_counters (
            agent TEXT NOT NULL,
            window_start TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (agent, window_start)
        );
    """),
]


async def current_version(db: Database) -> int:
    row = await db.fetchone(
        "SELECT value FROM schema_meta WHERE key = 'version'" if await _has_meta(db) else
        "SELECT 0 AS value"
    )
    return int(row["value"]) if row else 0


async def _has_meta(db: Database) -> bool:
    row = await db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
    )
    return row is not None


async def migrate(db: Database) -> int:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )
    """)
    cur = await current_version(db)
    applied = 0
    for m in MIGRATIONS:
        if m.version <= cur:
            continue
        if m.sql:
            await db._conn.executescript(m.sql)
            await db._conn.commit()
        await db.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
            (str(m.version),),
        )
        logger.info("applied migration %s: %s", m.version, m.description)
        applied += 1
    return applied