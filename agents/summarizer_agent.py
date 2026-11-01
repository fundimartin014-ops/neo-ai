"""Summarize text via the configured LLM. Supports modes: short|medium|bullets."""
from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from agents.llm import get_llm


_MODE_PROMPT = {
    "short":   "Produce a summary in 1-2 sentences. Be direct.",
    "medium":  "Produce a summary in 3-4 sentences. Preserve names and numbers.",
    "bullets": "Produce a summary as 3-6 concise bullet points. Each bullet on its own line, prefixed with '- '.",
}


SYSTEM = """You are a concise summarizer.
Never invent facts not present in the input.
Preserve names, numbers, and dates exactly."""


class SummarizerAgent(BaseAgent):
    name = "SummarizerAgent"
    capabilities = ("summarize",)

    MAX_CHARS = 9000

    def __init__(self, llm=None, **kw: Any) -> None:
        super().__init__(**kw)
        try:
            self.llm = llm or get_llm()
        except Exception:
            self.llm = None

    async def summarize(self, text: str, mode: str = "medium", focus: str = "") -> str:
        if not self.llm:
            return f"[summarizer] LLM not configured (input {len(text)} chars)"
        if not text or not text.strip():
            return "[summarizer] empty input"

        mode_key = (mode or "medium").strip().lower()
        mode_rule = _MODE_PROMPT.get(mode_key, _MODE_PROMPT["medium"])
        snippet = text[:self.MAX_CHARS]

        user = mode_rule + "\n\n"
        if focus:
            user += f"Focus on: {focus}\n\n"
        user += "Text to summarize:\n" + snippet

        try:
            return await self.llm.chat(
                [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": user}],
                temperature=0.3,
            )
        except Exception as e:
            return f"[summarizer error] {e}"

    async def arun(self, text: str, mode: str = "medium", focus: str = "") -> str:
        return await self.summarize(text, mode, focus)

    def run(self, text: str, mode: str = "medium", focus: str = "") -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run,
                                       self.summarize(text, mode, focus)).result()
            return loop.run_until_complete(self.summarize(text, mode, focus))
        except RuntimeError:
            return asyncio.run(self.summarize(text, mode, focus))

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "summarize":
            text = args[0] if args else ""
            mode = args[1] if len(args) > 1 else "medium"
            focus = args[2] if len(args) > 2 else ""
            return self.run(text, mode=mode, focus=focus)
        return f"SummarizerAgent - command '{command}' not implemented."
