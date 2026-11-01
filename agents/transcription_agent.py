"""TranscriptionAgent — speech-to-text via Groq Whisper (free tier).

Env:
  GROQ_API_KEY          -- required
  GROQ_WHISPER_MODEL    -- default whisper-large-v3
  GROQ_BASE_URL         -- default https://api.groq.com/openai/v1
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from agents.base_agent import BaseAgent


AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4", ".mpga")


class TranscriptionAgent(BaseAgent):
    name = "TranscriptionAgent"
    capabilities = ("transcribe",)

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)

    def transcribe(self, audio_path: str, language: str = "") -> str:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            return "[transcription error] GROQ_API_KEY not set in .env"

        p = Path(audio_path)
        if not p.is_absolute():
            here = Path(__file__).resolve().parent.parent
            for sub in ("sandbox", "generated_images", ""):
                cand = (here / sub / audio_path) if sub else (here / audio_path)
                if cand.exists():
                    p = cand
                    break
        if not p.exists():
            return f"[transcription error] file not found: {audio_path}"
        if not p.is_file():
            return f"[transcription error] not a file: {audio_path}"
        if p.suffix.lower() not in AUDIO_EXTS:
            return f"[transcription error] unsupported audio type: {p.suffix}"

        base = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        model = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

        try:
            with p.open("rb") as f:
                files = {
                    "file": (p.name, f, "application/octet-stream"),
                }
                data = {
                    "model": model,
                    "response_format": "json",
                }
                if language:
                    data["language"] = language
                headers = {"Authorization": f"Bearer {api_key}"}
                with httpx.Client(timeout=120) as client:
                    r = client.post(
                        f"{base}/audio/transcriptions",
                        headers=headers,
                        data=data,
                        files=files,
                    )
        except Exception as e:
            return f"[transcription error] request failed: {e}"

        if r.status_code != 200:
            return f"[transcription error] HTTP {r.status_code}: {r.text[:300]}"

        try:
            text = r.json().get("text", "").strip()
        except Exception as e:
            return f"[transcription error] parse failed: {e}"

        if not text:
            return "[transcription error] empty transcription"

        return text

    def run(self, audio_path: str = "", language: str = "") -> str:
        if not audio_path:
            return "TranscriptionAgent: provide an audio file path."
        return self.transcribe(audio_path, language=language)

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "transcribe":
            return self.run(args[0] if args else "")
        return f"TranscriptionAgent - command '{command}' not implemented."
