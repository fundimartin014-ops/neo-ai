"""Planner -> Executor -> Critic -> Memory wiring."""
import pytest

from agents.critic_agent import CriticAgent
from agents.executor_agent import ExecutorAgent
from agents.memory_agent import MemoryAgent
from agents.message_bus import MessageBus
from agents.persistence import MemoryRepository


class FakeBrowser:
    def open_page(self, url):
        return f"<html>fake page for {url}</html>"
    def search_and_extract(self, query):
        return f"fake search results for {query}"


@pytest.mark.asyncio
async def test_executor_routes_to_critic():
    bus = MessageBus()
    ex = ExecutorAgent(browser=FakeBrowser(), bus=bus)
    results = ex.run(["open https://example.com", "search for python"], goal="test")
    assert len(results) == 2
    msg = bus.receive("critic", timeout=0.5)
    assert msg is not None
    assert msg["type"] == "results"
    assert msg["goal"] == "test"


@pytest.mark.asyncio
async def test_critic_success_stores_to_memory():
    bus = MessageBus()
    critic = CriticAgent(bus=bus)
    results = [("step1", "a sufficiently long result"), ("step2", "another long result")]
    critic.run(results, goal="test")
    msg = bus.receive("memory", timeout=0.5)
    assert msg is not None
    assert msg["type"] == "store"
    assert msg["data"] == results


@pytest.mark.asyncio
async def test_critic_failure_replans():
    bus = MessageBus()
    critic = CriticAgent(bus=bus)
    critic.run([("step1", "")], goal="test")
    msg = bus.receive("planner", timeout=0.5)
    assert msg is not None
    assert msg["type"] == "goal"
    assert msg["data"] == "test"


@pytest.mark.asyncio
async def test_memory_agent_writes_to_db(db):
    bus = MessageBus()
    mem = MemoryAgent(repo=MemoryRepository(db), bus=bus)
    await mem.arun([("key1", "value1"), ("key2", "value2")])
    all_items = await mem.ahandle_command("all")
    assert "key1" in all_items
    assert "value1" in all_items
