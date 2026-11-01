"""DeviceControlAgent — control IoT devices via webhooks or Blynk HTTP API.

Config: config/devices.json
  {
    "devices": {
      "name": {
        "type": "webhook" | "blynk",
        ...
      }
    }
  }

Commands (via run()):
  "list"                      — list configured devices
  "status <name>"             — HTTP GET the status_url
  "on <name>" | "turn on <name>"
  "off <name>" | "turn off <name>"
  "toggle <name>"             — flip a stored state and fire the opposite

Blynk API (free tier):
  https://blynk.cloud/external/api/update?token=TOKEN&V3=1
  https://blynk.cloud/external/api/get?token=TOKEN&V3
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from agents.base_agent import BaseAgent


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "devices.json"


class DeviceControlAgent(BaseAgent):
    name = "DeviceControlAgent"
    capabilities = ("device_control",)

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self._state: dict[str, str] = {}   # in-memory on/off per device

    # ------------------------------------------------------------------ config
    def _load_devices(self) -> dict:
        if not CONFIG_PATH.exists():
            return {}
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return data.get("devices", {}) or {}
        except Exception as e:
            self.logger.warning("[device] config parse failed: %s", e)
            return {}

    # --------------------------------------------------------------- transports
    def _webhook_fire(self, dev_name: str, dev: dict, on: bool) -> str:
        url = dev.get("url")
        method = (dev.get("method") or "POST").upper()
        payload = dev.get("payload_on" if on else "payload_off") or {}

        if not url:
            return f"[device error] '{dev_name}' has no url"
        try:
            with httpx.Client(timeout=10) as c:
                if method == "GET":
                    r = c.get(url, params=payload)
                else:
                    r = c.request(method, url, json=payload)
        except Exception as e:
            return f"[device error] {dev_name}: {e}"

        if r.status_code >= 400:
            return f"[device error] {dev_name}: HTTP {r.status_code} {r.text[:120]}"

        self._state[dev_name] = "on" if on else "off"
        verb = "ON" if on else "OFF"
        return f"[device] {dev_name} → {verb} (HTTP {r.status_code})"

    def _blynk_fire(self, dev_name: str, dev: dict, on: bool) -> str:
        token = (dev.get("token") or os.getenv("BLYNK_TOKEN", "")).strip()
        pin = (dev.get("pin") or "V0").strip()
        if not token:
            return f"[device error] {dev_name}: blynk token missing (config or BLYNK_TOKEN env)"
        value = "1" if on else "0"
        url = f"https://blynk.cloud/external/api/update?token={token}&{pin}={value}"
        try:
            with httpx.Client(timeout=10) as c:
                r = c.get(url)
        except Exception as e:
            return f"[device error] {dev_name}: {e}"
        if r.status_code >= 400:
            return f"[device error] {dev_name}: Blynk HTTP {r.status_code} {r.text[:120]}"
        self._state[dev_name] = "on" if on else "off"
        verb = "ON" if on else "OFF"
        return f"[device] {dev_name} ({pin}) → {verb}"

    def _fire(self, dev_name: str, on: bool) -> str:
        devices = self._load_devices()
        if dev_name not in devices:
            names = ", ".join(sorted(devices.keys())) or "(none configured)"
            return f"[device error] unknown device '{dev_name}'. Known: {names}"
        dev = devices[dev_name]
        t = (dev.get("type") or "webhook").lower()
        if t == "blynk":
            return self._blynk_fire(dev_name, dev, on)
        return self._webhook_fire(dev_name, dev, on)

    def _status(self, dev_name: str) -> str:
        devices = self._load_devices()
        dev = devices.get(dev_name)
        if not dev:
            return f"[device error] unknown device '{dev_name}'"
        if dev.get("type", "webhook").lower() == "blynk":
            token = (dev.get("token") or os.getenv("BLYNK_TOKEN", "")).strip()
            pin = (dev.get("pin") or "V0").strip()
            if not token:
                return "[device error] blynk token missing"
            url = f"https://blynk.cloud/external/api/get?token={token}&{pin}"
        else:
            url = dev.get("status_url")
            if not url:
                return f"[device] {dev_name} state: {self._state.get(dev_name, 'unknown')} (no status_url)"
        try:
            with httpx.Client(timeout=10) as c:
                r = c.get(url)
        except Exception as e:
            return f"[device error] {dev_name}: {e}"
        if r.status_code >= 400:
            return f"[device error] {dev_name}: HTTP {r.status_code}"
        return f"[device] {dev_name} status: {r.text[:200].strip() or '(empty)'}"

    # ------------------------------------------------------------------- runner
    def run(self, query: str = "") -> str:
        q = (query or "").strip()
        if not q:
            return "DeviceControlAgent: use 'list', 'status <name>', 'on <name>', 'off <name>', 'toggle <name>'."

        parts = q.split(maxsplit=1)
        verb = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if verb in ("list", "devices"):
            devices = self._load_devices()
            if not devices:
                return "(no devices configured in config/devices.json)"
            lines = ["Configured devices:"]
            for name, d in sorted(devices.items()):
                t = d.get("type", "webhook")
                desc = d.get("description", "")
                state = self._state.get(name, "?")
                lines.append(f"  - {name}  [{t}]  state={state}  {desc}")
            return "\n".join(lines)

        if verb == "status":
            return self._status(rest) if rest else "[device error] missing device name"

        if verb == "on" or (verb == "turn" and rest.lower().startswith("on")):
            name = rest[3:].strip() if verb == "turn" else rest
            return self._fire(name, True)

        if verb == "off" or (verb == "turn" and rest.lower().startswith("off")):
            name = rest[4:].strip() if verb == "turn" else rest
            return self._fire(name, False)

        if verb == "toggle":
            current = self._state.get(rest, "off")
            return self._fire(rest, current != "on")

        return f"DeviceControlAgent: unknown verb '{verb}'. Try 'list' / 'on <name>' / 'off <name>'."

    def handle_command(self, command: str, *args: Any) -> str:
        if command == "list":
            return self.run("list")
        if command in ("on", "off", "toggle", "status") and args:
            return self.run(f"{command} {args[0]}")
        return f"DeviceControlAgent - command '{command}' not implemented."
