import pytest

from agents.browser import SimpleBrowser
from agents.critic_agent import CriticAgent
from agents.executor_agent import ExecutorAgent
from agents.memory_agent import MemoryAgent
from agents.message_bus import MessageBus
from agents.persistence import MemoryRepository
from agents.planner_agent import PlannerAgent


@pytest.mark.asyncio
async def test_pipeline_end_to_end(db):
    bus = MessageBus()
    mem_repo = MemoryRepository(db)

    planner = PlannerAgent(bus=bus)
    executor = ExecutorAgent(browser=SimpleBrowser(), bus=bus)
    critic = CriticAgent(bus=bus)
    memory = MemoryAgent(repo=mem_repo, bus=bus)

    # 1. plan
    await planner.arun("open https://python.org, open https://pypi.org")
    plan_msg = bus.receive("executor", timeout=0.5)
    assert plan_msg and plan_msg["type"] == "plan"
    assert len(plan_msg["data"]) == 2

    # 2. execute
    results = executor.run(plan_msg["data"], plan_msg["goal"])
    critic_msg = bus.receive("critic", timeout=0.5)
    assert critic_msg and critic_msg["type"] == "results"

    # 3. critique → memory (results are long strings, so it should pass)
    critic.run(critic_msg["data"], critic_msg["goal"])
    store_msg = bus.receive("memory", timeout=0.5)
    assert store_msg and store_msg["type"] == "store"

    # 4. store
    await memory.arun(store_msg["data"])
    stored = await mem_repo.all()
    assert len(stored) == 2