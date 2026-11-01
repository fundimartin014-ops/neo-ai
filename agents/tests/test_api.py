import pytest
from httpx import ASGITransport, AsyncClient

from agents.api_server import app


@pytest.mark.asyncio
async def test_health_and_command():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "AuditAgent" in body["agents"]
        assert r.headers["x-trace-id"]

        r2 = await client.post(
            "/command",
            json={"agent": "SentimentAgent", "command": "analyze", "args": ["I love this"]},
        )
        assert r2.status_code == 200
        assert r2.json()["ok"] is True
        assert r2.json()["result"] == "positive"


@pytest.mark.asyncio
async def test_unknown_agent_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/command", json={"agent": "NopeAgent", "command": "x", "args": []}
        )
        assert r.status_code == 404