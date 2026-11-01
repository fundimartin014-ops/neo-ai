"""Provider-agnostic LLM client. OpenAI-compatible endpoint by default."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.timeout = timeout

    async def chat(self, messages: list[dict], temperature: float = 0.0, **kwargs: Any) -> str:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY not set")
        payload = {"model": self.model, "messages": messages, "temperature": temperature, **kwargs}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]

    async def chat_json(self, messages: list[dict], schema: dict | None = None, **kwargs: Any) -> Any:
        body = await self.chat(messages, **kwargs)
        # strip common fences
        body = body.strip()
        if body.startswith("```"):
            body = body.split("```", 2)[1]
            if body.startswith("json"):
                body = body[4:]
            body = body.rsplit("```", 1)[0]
        return json.loads(body)


_singleton: LLMClient | None = None


def get_llm() -> LLMClient:
    global _singleton
    if _singleton is None:
        _singleton = LLMClient()
    return _singleton