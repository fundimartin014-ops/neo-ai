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