"""SQLite repository round-trips."""
import pytest

from agents.persistence import (
    AuditRepository,
    MemoryRepository,
    MetricsRepository,
    SessionRepository,
)
from agents.schemas import AuditEntry, MemoryItem, Metric


@pytest.mark.asyncio
async def test_audit_add_and_recent(db):
    repo = AuditRepository(db)
    await repo.add(AuditEntry(event="login", details={"user": "a"}))
    await repo.add(AuditEntry(event="logout"))
    rows = await repo.recent(limit=10)
    assert len(rows) == 2
    assert rows[0]["event"] == "logout"
    assert rows[1]["event"] == "login"


@pytest.mark.asyncio
async def test_audit_filter_by_event(db):
    repo = AuditRepository(db)
    await repo.add(AuditEntry(event="login"))
    await repo.add(AuditEntry(event="logout"))
    await repo.add(AuditEntry(event="login"))
    logins = await repo.recent(event="login")
    assert len(logins) == 2


@pytest.mark.asyncio
async def test_session_upsert_and_get(db):
    repo = SessionRepository(db)
    await repo.upsert("s1", {"name": "alice"})
    await repo.upsert("s1", {"name": "bob"})
    assert await repo.get("s1") == {"name": "bob"}
    await repo.delete("s1")
    assert await repo.get("s1") is None


@pytest.mark.asyncio
async def test_memory_store_and_search(db):
    repo = MemoryRepository(db)
    await repo.store(MemoryItem(key="py", value="python rocks"))
    await repo.store(MemoryItem(key="rs", value="rust is fast"))
    hits = await repo.search("python")
    assert len(hits) == 1
    assert hits[0]["key"] == "py"


@pytest.mark.asyncio
async def test_metrics_summary(db):
    repo = MetricsRepository(db)
    await repo.add(Metric(name="latency", value=10))
    await repo.add(Metric(name="latency", value=20))
    summary = await repo.summary()
    assert len(summary) == 1
    assert summary[0]["count"] == 2
    assert summary[0]["total"] == 30
    assert summary[0]["avg"] == 15
