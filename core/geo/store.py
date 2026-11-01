"""Geo store — properties, boundaries, cameras.

Everything is local. SQLite for structured data, GeoJSON for boundaries.
Coordinates are WGS84 (lat/lng), the same system Google Maps uses.
"""
from __future__ import annotations
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("data") / "geo.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    c = _conn()
    cur = c.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            kind        TEXT NOT NULL,     -- farm | house | plot | building | other
            notes       TEXT DEFAULT '',
            center_lat  REAL,
            center_lng  REAL,
            area_m2     REAL,
            tags        TEXT DEFAULT '[]', -- JSON array
            created     REAL,
            updated     REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS boundaries (
            id          TEXT PRIMARY KEY,
            property_id TEXT NOT NULL,
            geojson     TEXT NOT NULL,     -- {type: Polygon, coordinates: [[[lng,lat],...]]}
            label       TEXT DEFAULT '',
            created     REAL,
            FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            kind        TEXT NOT NULL,     -- frigate | rtsp | onvif | url
            endpoint    TEXT NOT NULL,
            lat         REAL,
            lng         REAL,
            facing_deg  REAL,
            enabled     INTEGER DEFAULT 1,
            notes       TEXT DEFAULT '',
            created     REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id          TEXT PRIMARY KEY,
            source      TEXT NOT NULL,     -- camera | satellite | manual
            camera_id   TEXT,
            kind        TEXT NOT NULL,     -- person | vehicle | animal | anomaly
            confidence  REAL,
            lat         REAL,
            lng         REAL,
            payload     TEXT,
            ts          REAL
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS ix_obs_ts ON observations(ts DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_obs_src ON observations(source)")
    c.commit()
    c.close()


# ---------- properties ----------
def add_property(name: str, kind: str, lat: float = None, lng: float = None,
                 notes: str = "", tags: List[str] = None) -> Dict[str, Any]:
    pid = uuid.uuid4().hex[:12]
    now = time.time()
    c = _conn()
    c.execute(
        "INSERT INTO properties(id,name,kind,notes,center_lat,center_lng,tags,created,updated) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (pid, name, kind, notes, lat, lng, json.dumps(tags or []), now, now),
    )
    c.commit()
    c.close()
    return get_property(pid)


def get_property(pid: str) -> Optional[Dict[str, Any]]:
    c = _conn()
    row = c.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
    if not row:
        c.close()
        return None
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["boundaries"] = list_boundaries(pid)
    c.close()
    return d


def list_properties() -> List[Dict[str, Any]]:
    c = _conn()
    rows = c.execute("SELECT * FROM properties ORDER BY updated DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags") or "[]")
        d["boundary_count"] = c.execute(
            "SELECT COUNT(*) FROM boundaries WHERE property_id=?", (d["id"],)
        ).fetchone()[0]
        out.append(d)
    c.close()
    return out


def delete_property(pid: str) -> bool:
    c = _conn()
    c.execute("DELETE FROM boundaries WHERE property_id=?", (pid,))
    n = c.execute("DELETE FROM properties WHERE id=?", (pid,)).rowcount
    c.commit()
    c.close()
    return n > 0


# ---------- boundaries ----------
def add_boundary(property_id: str, geojson: Dict[str, Any], label: str = "") -> Dict[str, Any]:
    bid = uuid.uuid4().hex[:12]
    c = _conn()
    c.execute(
        "INSERT INTO boundaries(id,property_id,geojson,label,created) VALUES (?,?,?,?,?)",
        (bid, property_id, json.dumps(geojson), label, time.time()),
    )
    # recompute center + area
    _recompute_property_geometry(property_id, c)
    c.commit()
    c.close()
    return {"id": bid, "property_id": property_id, "geojson": geojson, "label": label}


def list_boundaries(property_id: str) -> List[Dict[str, Any]]:
    c = _conn()
    rows = c.execute(
        "SELECT * FROM boundaries WHERE property_id=? ORDER BY created", (property_id,)
    ).fetchall()
    c.close()
    return [{"id": r["id"], "geojson": json.loads(r["geojson"]),
             "label": r["label"], "created": r["created"]} for r in rows]


def delete_boundary(bid: str) -> bool:
    c = _conn()
    row = c.execute("SELECT property_id FROM boundaries WHERE id=?", (bid,)).fetchone()
    if not row:
        c.close()
        return False
    c.execute("DELETE FROM boundaries WHERE id=?", (bid,))
    _recompute_property_geometry(row["property_id"], c)
    c.commit()
    c.close()
    return True


def _recompute_property_geometry(property_id: str, c: sqlite3.Connection) -> None:
    rows = c.execute("SELECT geojson FROM boundaries WHERE property_id=?", (property_id,)).fetchall()
    if not rows:
        return
    all_lats, all_lngs = [], []
    area = 0.0
    for r in rows:
        gj = json.loads(r["geojson"])
        coords = gj.get("coordinates") or []
        for ring in coords:
            all_lngs.extend(p[0] for p in ring)
            all_lats.extend(p[1] for p in ring)
            area += _polygon_area_m2(ring)
    if all_lats and all_lngs:
        c.execute(
            "UPDATE properties SET center_lat=?, center_lng=?, area_m2=?, updated=? WHERE id=?",
            (sum(all_lats)/len(all_lats), sum(all_lngs)/len(all_lngs), area, time.time(), property_id),
        )


def _polygon_area_m2(ring: List[List[float]]) -> float:
    """Approximate polygon area in m^2 using the spherical excess formula."""
    if len(ring) < 3:
        return 0.0
    import math
    R = 6378137.0
    total = 0.0
    for i in range(len(ring) - 1):
        lng1, lat1 = ring[i][0], ring[i][1]
        lng2, lat2 = ring[i+1][0], ring[i+1][1]
        total += math.radians(lng2 - lng1) * (
            2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2))
        )
    return abs(total * R * R / 2.0)


# ---------- cameras ----------
def add_camera(name: str, kind: str, endpoint: str,
               lat: float = None, lng: float = None,
               facing_deg: float = None, notes: str = "") -> Dict[str, Any]:
    cid = uuid.uuid4().hex[:12]
    c = _conn()
    c.execute(
        "INSERT INTO cameras(id,name,kind,endpoint,lat,lng,facing_deg,notes,created) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (cid, name, kind, endpoint, lat, lng, facing_deg, notes, time.time()),
    )
    c.commit()
    c.close()
    return {"id": cid, "name": name, "kind": kind, "endpoint": endpoint,
            "lat": lat, "lng": lng, "facing_deg": facing_deg}


def list_cameras() -> List[Dict[str, Any]]:
    c = _conn()
    rows = c.execute("SELECT * FROM cameras ORDER BY created DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


def delete_camera(cid: str) -> bool:
    c = _conn()
    n = c.execute("DELETE FROM cameras WHERE id=?", (cid,)).rowcount
    c.commit()
    c.close()
    return n > 0


# ---------- observations ----------
def add_observation(source: str, kind: str, confidence: float,
                    lat: float, lng: float, camera_id: str = None,
                    payload: Dict[str, Any] = None) -> Dict[str, Any]:
    oid = uuid.uuid4().hex[:12]
    c = _conn()
    c.execute(
        "INSERT INTO observations(id,source,camera_id,kind,confidence,lat,lng,payload,ts) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (oid, source, camera_id, kind, confidence, lat, lng,
         json.dumps(payload or {}), time.time()),
    )
    c.commit()
    c.close()
    return {"id": oid, "source": source, "kind": kind,
            "confidence": confidence, "lat": lat, "lng": lng}


def recent_observations(limit: int = 100) -> List[Dict[str, Any]]:
    c = _conn()
    rows = c.execute(
        "SELECT * FROM observations ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    c.close()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.get("payload") or "{}")
        out.append(d)
    return out


init_db()
