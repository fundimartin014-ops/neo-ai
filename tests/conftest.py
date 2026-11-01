"""Shared pytest fixtures and sys.path setup."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
import pytest_asyncio

from agents.message_bus import MessageBus
from agents.persistence import Database


@pytest_asyncio.fixture
async def db():
    d = Database(":memory:")
    await d.connect()
    yield d
    await d.close()


@pytest.fixture
def bus():
    b = MessageBus()
    yield b
    b.stop()
