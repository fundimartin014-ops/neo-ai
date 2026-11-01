"""Individual agent behaviour."""
import pytest

from agents.audit_agent import AuditAgent
from agents.memory_agent import MemoryAgent
from agents.metrics_agent import MetricsAgent
from agents.persistence import (
    AuditRepository,
    MemoryRepository,
    MetricsRepository,
    SessionRepository,
)
from agents.sentiment_agent import SentimentAgent
from agents.session_agent import SessionAgent


def test_sentiment_positive():
    assert SentimentAgent().run("I love this project") == "positive"


def test_sentiment_negative():
    assert SentimentAgent().run("this is terrible and broken") == "negative"


def test_sentiment_neutral():
    assert SentimentAgent().run("the sky is blue") == "neutral"


def test_sentiment_via_command():
    assert SentimentAgent().handle_command("analyze", "I love it") == "positive"


@pytest.mark.asyncio
async def test_audit_agent_records(db):
    a = AuditAgent(repo=AuditRepository(db))
    await a.arun("test_event", {"k": "v"})
    result = await a.ahandle_command("recent")
    assert "test_event" in result


@pytest.mark.asyncio
async def test_memory_agent_stores(db):
    a = MemoryAgent(repo=MemoryRepository(db))
    await a.arun([("step1", "some result"), ("step2", "another result")])
    all_items = await a.ahandle_command("all")
    assert "step1" in all_items
    assert "step2" in all_items


@pytest.mark.asyncio
async def test_metrics_agent_summary(db):
    a = MetricsAgent(repo=MetricsRepository(db))
    await a.arun("test_metric", 5.0)
    await a.arun("test_metric", 15.0)
    summary = await a.ahandle_command("summary")
    assert "test_metric" in summary


@pytest.mark.asyncio
async def test_session_agent_lifecycle(db):
    a = SessionAgent(repo=SessionRepository(db))
    await a.arun("sess1", {"user": "alice"})
    got = await a.arun("sess1")
    assert "alice" in got
