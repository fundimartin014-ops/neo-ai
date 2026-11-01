"""Real Frigate API client.

Talks to a local Frigate NVR over its HTTP API. Does not require Frigate to
be running — every method returns a structured result even when offline.
"""
from __future__ import annotations
import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

log = logging.getLogger("cameras.frigate")


class FrigateClient:
    def __init__(self, url: Optional[str] = None, timeout: int = 5):
        self.url = (url or os.getenv("FRIGATE_URL", "http://127.0.0.1:5000")).rstrip("/")
        self.timeout = timeout

    # ---------- connectivity ----------
    def online(self) -> bool:
        try:
            self._get("/api/version")
            return True
        except Exception:
            return False

    def version(self) -> Dict[str, Any]:
        try:
            return {"online": True, "version": self._get("/api/version"),
                    "url": self.url}
        except Exception as e:
            return {"online": False, "url": self.url, "error": str(e)}

    # ---------- cameras ----------
    def cameras(self) -> List[str]:
        try:
            cfg = self._get("/api/config")
            return list((cfg.get("cameras") or {}).keys())
        except Exception as e:
            log.debug("[frigate] cameras failed: %s", e)
            return []

    # ---------- events ----------
    def events(self, limit: int = 50,
               labels: Optional[List[str]] = None,
               after: Optional[int] = None) -> List[Dict[str, Any]]:
        params = [f"limit={limit}"]
        if labels:
            for lbl in labels:
                params.append(f"labels={lbl}")
        if after:
            params.append(f"after={after}")
        try:
            return self._get("/api/events?" + "&".join(params)) or []
        except Exception as e:
            log.debug("[frigate] events failed: %s", e)
            return []

    def latest_event(self, camera: Optional[str] = None,
                     label: Optional[str] = None) -> Optional[Dict[str, Any]]:
        evs = self.events(limit=1, labels=[label] if label else None)
        if camera:
            evs = [e for e in evs if e.get("camera") == camera]
        return evs[0] if evs else None

    # ---------- snapshots ----------
    def snapshot_bytes(self, event_id: str) -> Optional[bytes]:
        try:
            return self._get_raw(f"/api/events/{event_id}/snapshot.jpg")
        except Exception as e:
            log.debug("[frigate] snapshot failed: %s", e)
            return None

    # ---------- helpers ----------
    def _get(self, path: str) -> Any:
        raw = self._get_raw(path)
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return raw.decode("utf-8", errors="replace")

    def _get_raw(self, path: str) -> Optional[bytes]:
        url = self.url + path
        req = urllib.request.Request(
            url, headers={"User-Agent": "Neo/1.0", "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        except Exception:
            raise


# ---------- Neo integration ----------
def sync_to_store(client: Optional[FrigateClient] = None) -> Dict[str, Any]:
    """Read recent Frigate events, write them as observations in the geo store."""
    from core.geo import store
    c = client or FrigateClient()

    events = c.events(limit=50)
    cams_by_name = {cam["name"]: cam for cam in store.list_cameras()}
    written = 0
    skipped = 0

    for ev in events:
        cam = cams_by_name.get(ev.get("camera", ""))
        if not cam:
            skipped += 1
            continue
        store.add_observation(
            source="camera",
            kind=ev.get("label", "object"),
            confidence=float(ev.get("data", {}).get("top_score", 0) or 0),
            lat=cam.get("lat") or 0.0,
            lng=cam.get("lng") or 0.0,
            camera_id=cam["id"],
            payload={
                "frigate_id": ev.get("id"),
                "start_time": ev.get("start_time"),
                "end_time": ev.get("end_time"),
                "zones": ev.get("zones", []),
                "has_snapshot": ev.get("has_snapshot", False),
            },
        )
        written += 1

    return {
        "online": c.online(),
        "written": written,
        "skipped_no_camera": skipped,
        "total_events": len(events),
    }
