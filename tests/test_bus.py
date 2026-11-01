"""MessageBus behaviour."""
from agents.message_bus import MessageBus, SHUTDOWN


def test_send_receive():
    bus = MessageBus()
    bus.send("inbox1", {"type": "hello", "data": 42})
    msg = bus.receive("inbox1", timeout=0.5)
    assert msg["type"] == "hello"
    assert msg["data"] == 42
    assert "trace_id" in msg


def test_stop_emits_shutdown():
    bus = MessageBus()
    bus.register("a")
    bus.stop()
    msg = bus.receive("a", timeout=0.5)
    assert msg["type"] == SHUTDOWN
    assert bus.stopped is True


def test_publish_subscribe():
    bus = MessageBus()
    got = []
    bus.subscribe("evt", got.append)
    bus.publish("evt", "payload")
    assert got == ["payload"]


def test_publish_isolates_failures():
    bus = MessageBus()
    got = []
    def boom(_):
        raise RuntimeError("bad handler")
    bus.subscribe("evt", boom)
    bus.subscribe("evt", got.append)
    bus.publish("evt", "ok")
    assert got == ["ok"]
