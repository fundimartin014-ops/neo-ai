from __future__ import annotations

from agents.env_loader import load_env
load_env()  # populate os.environ from .env (shell env wins)
import asyncio
import sys

from agents.api_server import build_registry
from agents.config import Config
from agents.logging_setup import setup_logging
from agents.message_bus import MessageBus
from agents.persistence import Database


async def _run(goal: str) -> None:
    Config.ensure_dirs()
    setup_logging(level=Config.LOG_LEVEL, json_output=Config.LOG_JSON)

    db = Database(Config.DB_PATH)
    await db.connect()
    bus = MessageBus()
    registry = build_registry(bus=bus, db=db)

    for name in ("ExecutorAgent", "CriticAgent", "MemoryAgent"):
        agent = registry.get(name)
        if agent and hasattr(agent, "start"):
            agent.start()

    try:
        print("-> goal:", goal)
        plan_result = await registry.arun("PlannerAgent", goal)
        print("-> plan:", plan_result)

        # wait for the executor -> critic -> memory pipeline to settle
        await asyncio.sleep(4.0)

        print("-> memory (latest 3):")
        mem = await registry.acommand("MemoryAgent", "all")
        print(mem[:400] + ("..." if len(mem) > 400 else ""))
    finally:
        bus.stop()
        registry.shutdown()
        await db.close()


def main() -> None:
    goal = " ".join(sys.argv[1:]) or "I love this project"
    asyncio.run(_run(goal))


if __name__ == "__main__":
    main()