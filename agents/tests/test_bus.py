from agents.message_bus import MessageBus
from agents.schemas import MessageType


def test_send_receive():
    bus = MessageBus()
    bus.send("a", {"type": "hello"})
    msg = bus.receive("a", timeout=0.1)
    assert msg["type"] == "hello"
    assert "trace_id" in msg


def test_stop_emits_shutdown():
    bus = MessageBus()
    bus.register("a")
    bus.stop()
    msg = bus.receive("a", timeout=0.1)
    assert msg["type"] == MessageType.SHUTDOWN.value


def test_pubsub():
    bus = MessageBus()
    got = []
    bus.subscribe("x", got.append)
    bus.publish("x", 42)
    bus.unsubscribe("x", got.append)
    bus.publish("x", 99)
    assert got == [42]


def test_pubsub_isolation():
    bus = MessageBus()
    got = []
    bus.subscribe("x", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    bus.subscribe("x", got.append)
    bus.publish("x", "ok")
    assert got == ["ok"]