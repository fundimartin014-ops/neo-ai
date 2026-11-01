"""Camera integration — Frigate NVR, RTSP, ONVIF.

Frigate is an open-source NVR that runs local AI object detection on IP
camera streams (no cloud, no subscription). This module:

  * Registers cameras into the geo store
  * Talks to a local Frigate instance via its HTTP API (default :5000)
  * Pulls recent events (person / vehicle / animal detections)
  * Writes them into the observations table for the map to display

To run Frigate, see docs/CAMERAS.md (single docker-compose).
"""
from __future__ import annotations
import os
import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional

from core.geo import store

log = logging.getLogger("geo.cameras")

FRIGATE_URL = os.getenv("FRIGATE_URL", "http://127.0.0.1:5000").rstrip("/")


def frigate_status() -> Dict[str, Any]:
    """Ping the local Frigate instance."""
    try:
        with urllib.request.urlopen(f"{FRIGATE_URL}/api/version", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
            return {"online": True, "version": data.get("version", "?"), "url": FRIGATE_URL}
    except Exception as e:
        return {"online": False, "url": FRIGATE_URL, "error": str(e)}


def frigate_events(limit: int = 20) -> List[Dict[str, Any]]:
    """Pull recent events from Frigate (person/vehicle/etc.)."""
    try:
        with urllib.request.urlopen(f"{FRIGATE_URL}/api/events?limit={limit}", timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        log.warning("[cameras] frigate events failed: %s", e)
        return []


def sync_frigate_observations() -> Dict[str, Any]:
    """Read recent Frigate events, write them into observations."""
    events = frigate_events(limit=50)
    written = 0
    cams = {c["name"]: c for c in store.list_cameras()}
    for ev in events:
        cam_name = ev.get("camera", "")
        cam = cams.get(cam_name)
        if not cam:
            continue
        store.add_observation(
            source="camera",
            kind=ev.get("label", "unknown"),
            confidence=float(ev.get("data", {}).get("top_score", 0) or 0),
            lat=cam.get("lat") or 0.0,
            lng=cam.get("lng") or 0.0,
            camera_id=cam["id"],
            payload={
                "frigate_id": ev.get("id"),
                "start_time": ev.get("start_time"),
                "end_time": ev.get("end_time"),
                "zones": ev.get("zones", []),
            },
        )
        written += 1
    return {"written": written, "total_events": len(events)}
