from pathlib import Path

content = '''"""SpeechAgent — text-to-speech via Windows System.Speech (no pip install)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SANDBOX = PROJECT_ROOT / "sandbox"


def _find_powershell() -> str | None:
    """Locate powershell.exe even when not on PATH (UCRT64, Git Bash, etc.)."""
    candidates = [
        shutil.which("powershell.exe"),
        shutil.which("powershell"),
        r"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        r"C:\\Windows\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe",
        r"C:\\Program Files\\PowerShell\\7\\pwsh.exe",
        shutil.which("pwsh.exe"),
        shutil.which("pwsh"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


class SpeechAgent(BaseAgent):
    name = "SpeechAgent"
    capabilities = ("speak", "tts")

    def _powershell_speak(self, text: str, output_path: str | None = None) -> str:
        ps = _find_powershell()
        if not ps:
            return "[speech error] powershell.exe not found on this system"

        # Escape single quotes for PowerShell single-quoted string
        safe = text.replace("'", "''")
        # Also ensure the WAV path has forward slashes if any (PowerShell accepts both)
        out = (output_path or "").replace("\\\\", "/")

        parts = [
            "Add-Type -AssemblyName System.Speech",
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        ]
        if out:
            parts.append(f"$s.SetOutputToWaveFile('{out}')")
            parts.append(f"$s.Speak('{safe}')")
            parts.append("$s.Dispose()")
            parts.append("Write-Output 'SAVED'")
        else:
            parts.append(f"$s.Speak('{safe}')")
            parts.append("$s.Dispose()")
            parts.append("Write-Output 'SPOKEN'")

        script = "; ".join(parts) + ";"

        try:
            result = subprocess.run(
                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            return "[speech error] timeout"
        except Exception as e:
            return f"[speech error] {e}"

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return f"[speech error] {detail[:300]}"

        return (result.stdout or "").strip()

    def speak(self, text: str) -> str:
        if not text.strip():
            return "[speech error] empty text"
        if sys.platform != "win32":
            return "[speech error] server-side TTS is Windows-only"
        if len(text) > 4000:
            text = text[:4000] + " ... (truncated)"
        out = self._powershell_speak(text)
        if out == "SPOKEN":
            return f"[spoken] {len(text)} chars"
        return out or "[speech error] unknown failure"

    def save(self, text: str, filename: str = "") -> str:
        if not text.strip():
            return "[speech error] empty text"
        if sys.platform != "win32":
            return "[speech error] server-side TTS is Windows-only"

        SANDBOX.mkdir(parents=True, exist_ok=True)
        if not filename:
            import time
            filename = f"speech_{int(time.time())}.wav"
        if not filename.lower().endswith(".wav"):
            filename += ".wav"

        target = SANDBOX / filename
        out = self._powershell_speak(text, str(target))
        if out == "SAVED" and target.exists():
            size = target.stat().st_size
            return f"[saved] {target.relative_to(PROJECT_ROOT)} ({size} bytes)"
        return out or "[speech error] save failed"

    def run(self, query: str = "") -> str:
        q = (query or "").strip()
        if not q:
            return "SpeechAgent: provide text to speak."
        if q.lower().startswith("save:"):
            return self.save(q[5:].strip())
        if q.lower().startswith("file:"):
            body = q[5:].strip()
            if "|" in body:
                text, name = body.split("|", 1)
                return self.save(text.strip(), name.strip())
            return self.save(body)
        return self.speak(q)

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "speak":
            return self.speak(args[0] if args else "")
        if command == "save":
            return self.save(args[0] if args else "",
                             args[1] if len(args) > 1 else "")
        return f"SpeechAgent - command '{command}' not implemented."
'''

Path("agents/speech_agent.py").write_text(content, encoding="utf-8")
print("Rewrote agents/speech_agent.py with absolute PowerShell path")