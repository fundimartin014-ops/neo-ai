"""Home Assistant REST client + natural-language router.

Reads entity states and calls services on a local HA instance. Includes a
simple intent parser so "turn on garden lights" maps to light.turn_on on the
right entities.
"""
from __future__ import annotations
import json
import logging
import os
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

log = logging.getLogger("devices.ha")


class HomeAssistant:
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None,
                 timeout: int = 8):
        self.url = (url or os.getenv("HOME_ASSISTANT_URL", "http://127.0.0.1:8123")).rstrip("/")
        self.token = token or os.getenv("HOME_ASSISTANT_TOKEN", "")
        self.timeout = timeout
        self._states_cache: Optional[List[Dict[str, Any]]] = None

    # ---------- connectivity ----------
    def online(self) -> bool:
        if not self.token:
            return False
        try:
            self._get("/api/")
            return True
        except Exception:
            return False

    def status(self) -> Dict[str, Any]:
        info = {"url": self.url, "token_set": bool(self.token), "online": False}
        if not self.token:
            info["hint"] = "set HOME_ASSISTANT_TOKEN in .env"
            return info
        try:
            data = self._get("/api/")
            info["online"] = True
            info["message"] = data.get("message", "")
            info["states"] = self._get("/api/states")
            info["entity_count"] = len(info["states"])
        except Exception as e:
            info["error"] = str(e)
        return info

    # ---------- entities ----------
    def states(self, refresh: bool = False) -> List[Dict[str, Any]]:
        if refresh or self._states_cache is None:
            try:
                self._states_cache = self._get("/api/states") or []
            except Exception as e:
                log.debug("[ha] states failed: %s", e)
                self._states_cache = []
        return self._states_cache

    def by_domain(self, domain: str) -> List[Dict[str, Any]]:
        return [s for s in self.states() if s["entity_id"].startswith(f"{domain}.")]

    def find(self, query: str) -> List[Dict[str, Any]]:
        """Fuzzy match entity by friendly name or entity_id substring."""
        q = query.lower().strip()
        if not q:
            return []
        tokens = [t for t in re.split(r"\s+", q) if t and t not in
                  ("the", "a", "an", "my", "all")]
        matches = []
        for s in self.states():
            name = (s.get("attributes", {}).get("friendly_name", "") or "").lower()
            eid = s["entity_id"].lower()
            if all(tok in name or tok in eid for tok in tokens):
                matches.append(s)
        return matches

    # ---------- services ----------
    def call(self, domain: str, service: str,
             entity_id: Optional[str] = None,
             data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = dict(data or {})
        if entity_id:
            body["entity_id"] = entity_id
        try:
            return self._post(f"/api/services/{domain}/{service}", body)
        except Exception as e:
            return {"error": str(e)}

    # ---------- intent router ----------
    _ON = re.compile(r"\b(turn\s+on|switch\s+on|enable|start|open)\b", re.I)
    _OFF = re.compile(r"\b(turn\s+off|switch\s+off|disable|stop|close|kill)\b", re.I)
    _TOGGLE = re.compile(r"\b(toggle|flip)\b", re.I)
    _SET_TEMP = re.compile(r"set\s+(?:the\s+)?(.+?)\s+temperature\s+to\s+([\d.]+)", re.I)
    _SET_BRIGHT = re.compile(r"(?:set\s+)?(.+?)\s+(?:brightness|dim)\s+(?:to\s+)?([\d]+)%", re.I)

    def handle(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "Usage: home: <command>"

        low = text.lower()
        if low in ("status", "list"):
            return self._status_summary()
        if low in ("lights", "list lights"):
            return self._list_domain("light")
        if low in ("switches", "list switches"):
            return self._list_domain("switch")
        if low in ("climate", "thermostats"):
            return self._list_domain("climate")

        # set temperature
        m = self._SET_TEMP.search(text)
        if m:
            name, temp = m.group(1), float(m.group(2))
            ents = self.find(name)
            if not ents:
                return f"[HA] no entity matched: {name!r}"
            for e in ents:
                self.call("climate", "set_temperature", e["entity_id"],
                          {"temperature": temp})
            return f"[HA] set {name} to {temp}°C ({len(ents)} entities)"

        # set brightness
        m = self._SET_BRIGHT.search(text)
        if m:
            name, pct = m.group(1), int(m.group(2))
            ents = [e for e in self.find(name) if e["entity_id"].startswith("light.")]
            if not ents:
                return f"[HA] no light matched: {name!r}"
            for e in ents:
                self.call("light", "turn_on", e["entity_id"],
                          {"brightness_pct": pct})
            return f"[HA] set {name} brightness to {pct}% ({len(ents)} lights)"

        # on / off / toggle
        if self._ON.search(text):
            return self._apply("on", text)
        if self._OFF.search(text):
            return self._apply("off", text)
        if self._TOGGLE.search(text):
            return self._apply("toggle", text)

        return (f"[HA] did not parse: {text!r}\n"
                "Try: 'turn on garden lights', 'set living room temperature to 22', "
                "'turn off all lights'")

    def _apply(self, action: str, text: str) -> str:
        # strip the verb to get the target
        name = re.sub(r"\b(turn\s+on|turn\s+off|switch\s+on|switch\s+off|"
                      r"enable|disable|toggle|flip|start|stop|open|close|kill)\b",
                      "", text, flags=re.I).strip()
        name = re.sub(r"^(the|my|all)\s+", "", name, flags=re.I).strip()

        if not name or name.lower() == "all":
            # apply to all lights + switches
            return self._apply_all(action)

        ents = self.find(name)
        if not ents:
            return f"[HA] no entity matched: {name!r}"

        svc_map = {"on": "turn_on", "off": "turn_off", "toggle": "toggle"}
        svc = svc_map[action]
        applied = 0
        for e in ents:
            domain = e["entity_id"].split(".")[0]
            if domain in ("light", "switch", "input_boolean", "fan", "media_player"):
                r = self.call(domain, svc, e["entity_id"])
                if "error" not in r:
                    applied += 1
        return f"[HA] {action} applied to {applied}/{len(ents)} entities for {name!r}"

    def _apply_all(self, action: str) -> str:
        svc_map = {"on": "turn_on", "off": "turn_off", "toggle": "toggle"}
        svc = svc_map[action]
        applied = 0
        for domain in ("light", "switch", "fan"):
            ents = [e for e in self.by_domain(domain)
                    if e.get("state") != "unavailable"]
            for e in ents:
                r = self.call(domain, svc, e["entity_id"])
                if "error" not in r:
                    applied += 1
        return f"[HA] {action} applied to {applied} entities (all)"

    def _status_summary(self) -> str:
        s = self.states(refresh=True)
        if not s:
            return "[HA] no entities (is HA online? check HOME_ASSISTANT_TOKEN)"
        from collections import Counter
        domains = Counter(e["entity_id"].split(".")[0] for e in s)
        lines = [f"[HA] {len(s)} entities:"]
        for d, n in sorted(domains.items(), key=lambda x: -x[1])[:12]:
            lines.append(f"  {d:<20} {n}")
        return "\n".join(lines)

    def _list_domain(self, domain: str) -> str:
        ents = self.by_domain(domain)
        if not ents:
            return f"[HA] no {domain} entities"
        lines = [f"[HA] {len(ents)} {domain} entities:"]
        for e in ents[:30]:
            name = e.get("attributes", {}).get("friendly_name", e["entity_id"])
            lines.append(f"  {e['state']:<12} {name}")
        return "\n".join(lines)

    # ---------- http ----------
    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, path: str) -> Any:
        req = urllib.request.Request(
            self.url + path, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            body = r.read()
            try:
                return json.loads(body.decode("utf-8"))
            except Exception:
                return body.decode("utf-8", errors="replace")

    def _post(self, path: str, data: Dict[str, Any]) -> Any:
        req = urllib.request.Request(
            self.url + path,
            data=json.dumps(data).encode("utf-8"),
            headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            body = r.read()
            if not body:
                return {"ok": True}
            try:
                return json.loads(body.decode("utf-8"))
            except Exception:
                return {"ok": True}
