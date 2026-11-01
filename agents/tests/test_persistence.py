import pytest

from agents.persistence import (
    AuditRepository,
    MemoryRepository,
    MetricsRepository,
    SessionRepository,
)
from agents.schemas import AuditEntry, MemoryItem, Metric


@pytest.mark.asyncio
async def test_audit_roundtrip(db):
    repo = AuditRepository(db)
    await repo.add(AuditEntry(event="login", details={"u": "a"}))
    await repo.add(AuditEntry(event="logout"))
    rows = await repo.recent()
    assert [r["event"] for r in rows] == ["logout", "login"]
    assert len(await repo.recent(event="login")) == 1


@pytest.mark.asyncio
async def test_session_upsert(db):
    repo = SessionRepository(db)
    await repo.upsert("s1", {"u": "a"})
    await repo.upsert("s1", {"u": "b"})
    assert await repo.get("s1") == {"u": "b"}
    await repo.delete("s1")
    assert await repo.get("s1") is None


@pytest.mark.asyncio
async def test_memory_search(db):
    repo = MemoryRepository(db)
    await repo.store(MemoryItem(key="py", value="python is great"))
    await repo.store(MemoryItem(key="rs", value="rust is fast"))
    hits = await repo.search("python")
    assert len(hits) == 1 and hits[0]["key"] == "py"


@pytest.mark.asyncio
async def test_metrics_summary(db):
    repo = MetricsRepository(db)
    await repo.add(Metric(name="latency_ms", value=10))
    await repo.add(Metric(name="latency_ms", value=20))
    summary = await repo.summary()
    assert summary[0]["count"] == 2
    assert summary[0]["avg"] == 15