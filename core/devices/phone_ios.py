"""iOS via Home Assistant Companion app."""
from __future__ import annotations
import logging, os
from typing import Any, Dict, List

log = logging.getLogger("devices.ios")


class iPhone:
    def __init__(self):
        self.ha_url = os.getenv("HOME_ASSISTANT_URL", "http://127.0.0.1:8123").rstrip("/")
        self.ha_token = os.getenv("HOME_ASSISTANT_TOKEN", "").strip()
        self.notify_service = os.getenv("HA_IOS_NOTIFY_SERVICE", "").strip()

    def available(self):
        return bool(self.ha_token and self.notify_service)

    def _post(self, domain, service, data):
        try:
            import requests
        except ImportError:
            return {"ok": False, "error": "requests not installed"}
        try:
            r = requests.post(f"{self.ha_url}/api/services/{domain}/{service}",
                              headers={"Authorization": f"Bearer {self.ha_token}",
                                       "Content-Type": "application/json"},
                              json=data, timeout=20)
            return {"ok": r.status_code < 300, "status": r.status_code}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _states(self):
        try:
            import requests
        except ImportError:
            return []
        try:
            r = requests.get(f"{self.ha_url}/api/states",
                             headers={"Authorization": f"Bearer {self.ha_token}"},
                             timeout=10)
            return r.json() if r.status_code < 300 else []
        except Exception:
            return []

    def status(self):
        if not self.ha_token:
            return ("[phone] iOS: HOME_ASSISTANT_TOKEN not set.\n"
                    "  Install HA Companion on iPhone, log into HA, then set env.")
        if not self.notify_service:
            return ("[phone] iOS: HA_IOS_NOTIFY_SERVICE not set.\n"
                    "  Find it in HA: Developer Tools -> Services -> filter mobile_app.")
        return f"[phone] iOS ready via {self.notify_service}"

    def notify(self, message, title="Neo"):
        if not self.available():
            return "[phone] iOS not configured"
        domain, _, svc = self.notify_service.partition(".")
        if not svc:
            return f"[phone] malformed service {self.notify_service!r}"
        r = self._post(domain, svc, {"message": message, "title": title})
        return "[phone] iOS notification sent" if r.get("ok") else f"[phone] iOS notify failed: {r}"

    def sensor(self, which="battery"):
        states = [s for s in self._states()
                  if "iphone" in s.get("entity_id", "").lower()
                  and which.lower() in s.get("entity_id", "").lower()]
        if not states:
            return f"[phone] no iOS sensor for {which!r}"
        return "[phone] iOS sensors:\n  " + "\n  ".join(
            f"{s['entity_id']} = {s.get('state', '?')}" for s in states[:6])


def handle(text):
    t = (text or "").strip()
    p = iPhone()
    if not t or t == "status":
        return p.status()
    parts = t.split(maxsplit=1)
    cmd, rest = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
    if cmd == "notify":   return p.notify(rest)
    if cmd == "sensor":   return p.sensor(rest.strip() or "battery")
    return "[phone] iOS: status | notify <msg> | sensor <type>"
