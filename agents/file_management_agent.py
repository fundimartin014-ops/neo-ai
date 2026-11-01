"""Sandboxed file agent. Handles both 2-arg and single-payload forms."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from agents.config import Config

_KNOWN_COMMANDS = {"read", "write", "list", "delete"}


class FileManagementAgent(BaseAgent):
    name = "FileManagementAgent"
    capabilities = ("file_read", "file_write", "file_list", "file_delete")

    def __init__(self, root: str = None, **kw):
        super().__init__(**kw)
        self.root = Path(root or Config.FILE_AGENT_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- safety -----------------------------------------------------------
    def _safe(self, user_path: str) -> Path:
        target = (self.root / user_path).resolve()
        if self.root != target and self.root not in target.parents:
            raise PermissionError(f"Path escapes sandbox: {user_path}")
        return target

    # ---- primitives -------------------------------------------------------
    def _read(self, p: str) -> str:
        try:
            return self._safe(p).read_text(encoding="utf-8")
        except Exception as e:
            return f"[read error] {e}"

    def _write(self, p: str, content: str) -> str:
        try:
            f = self._safe(p)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} bytes to {p}"
        except Exception as e:
            return f"[write error] {e}"

    def _list(self, p: str = ".") -> str:
        try:
            d = self._safe(p)
            return "\n".join(sorted(x.name for x in d.iterdir()))
        except Exception as e:
            return f"[list error] {e}"

    def _delete(self, p: str) -> str:
        try:
            f = self._safe(p)
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
            return f"Deleted {p}"
        except Exception as e:
            return f"[delete error] {e}"

    # ---- parsing ----------------------------------------------------------
    def _parse_payload(self, payload: str) -> tuple[str, str] | None:
        """Split 'path long content' into (path, content). Path = first token."""
        s = payload.strip()
        if not s:
            return None
        parts = s.split(None, 1)
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[1]

    def _detect_command(self, s: str) -> str | None:
        """Given 'write digests/x.md ...' or 'read file.txt', return the leading verb."""
        first = s.strip().split(None, 1)[0].lower()
        return first if first in _KNOWN_COMMANDS else None

    # ---- entry points -----------------------------------------------------
    def run(self, command_or_payload: str, *args: Any) -> str:
        # Form A: run("write", path, content)
        if args:
            cmd = command_or_payload.lower()
            if cmd == "write":
                return self._write(args[0], args[1])
            if cmd == "read":
                return self._read(args[0])
            if cmd == "list":
                return self._list(args[0] if args else ".")
            if cmd == "delete":
                return self._delete(args[0])
            return f"Unknown file command: {command_or_payload}"

        # Form B: run("write digests/x.md long content...")
        s = (command_or_payload or "").strip()
        cmd = self._detect_command(s)
        if cmd is None:
            return f"Unknown file command: {s[:80]}"

        # Strip the leading verb, keep the rest
        rest = s[len(cmd):].lstrip()

        if cmd == "write":
            parsed = self._parse_payload(rest)
            if parsed is None:
                return "[write error] no path"
            path, content = parsed
            return self._write(path, content)
        if cmd == "read":
            parsed = self._parse_payload(rest)
            return self._read(parsed[0]) if parsed else "[read error] no path"
        if cmd == "list":
            parsed = self._parse_payload(rest)
            return self._list(parsed[0] if parsed else ".")
        if cmd == "delete":
            parsed = self._parse_payload(rest)
            return self._delete(parsed[0]) if parsed else "[delete error] no path"

        return f"Unknown file command: {s[:80]}"

    def handle_command(self, command: str, *args: Any) -> str:
        return self.run(command, *args)
