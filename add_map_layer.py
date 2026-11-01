from pathlib import Path

root = Path(".").resolve()

# ============================================================
# core/geo/__init__.py
# ============================================================
(root / "core" / "geo").mkdir(parents=True, exist_ok=True)
(root / "core" / "geo" / "__init__.py").write_text(
    '"""Geo layer: property mapping, satellite imagery, cameras."""\n',
    encoding="utf-8",
)

# ============================================================
# core/geo/store.py — SQLite + GeoJSON storage
# ============================================================
store = r'''"""Geo store — properties, boundaries, cameras.

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
'''

(root / "core" / "geo" / "store.py").write_text(store, encoding="utf-8")
print("[ok] core/geo/store.py")

# ============================================================
# core/geo/tiles.py — tile server configuration
# ============================================================
tiles = r'''"""Tile server configuration — where the map gets its imagery.

Defaults to public vector tiles + free satellite. To go fully offline,
flip TILE_MODE = "local" and run the Martin/Planetiler stack (see
docs/SELFHOSTED_MAPS.md for the one-line docker-compose).
"""
from __future__ import annotations
import os
from typing import Dict, Any

TILE_MODE = os.getenv("NEO_TILE_MODE", "public")   # public | local


def config() -> Dict[str, Any]:
    """Return a MapLibre style spec + tile source config."""

    if TILE_MODE == "local":
        # Self-hosted tiles (Martin on :3000, Planetiler output in ./data/tiles)
        return {
            "mode": "local",
            "vector_tiles": "http://127.0.0.1:3000/{z}/{x}/{y}",
            "satellite_tiles": "http://127.0.0.1:8000/tiles/satellite/{z}/{x}/{y}.jpg",
            "attribution": "© OpenStreetMap contributors",
        }

    # Public defaults — both free, no key, no signup
    return {
        "mode": "public",
        # OpenFreeMap / Versatiles — free OSM vector tiles, no key
        "vector_tiles": "https://tiles.openfreemap.org/planet/20250122_001001_pt/{z}/{x}/{y}.pbf",
        "style_url": "https://tiles.openfreemap.org/styles/liberty",
        # EOX Sentinel-2 cloudless 2024 — free satellite imagery, no key
        "satellite_tiles": (
            "https://tiles.maps.eox.at/wmts/1.0.0/"
            "s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg"
        ),
        "attribution": (
            "Map: © OpenStreetMap contributors · "
            "Satellite: Sentinel-2 cloudless by EOX (CC BY-NC-SA 4.0)"
        ),
    }


def map_style() -> Dict[str, Any]:
    """Full MapLibre style spec with both basemap + satellite layers."""
    cfg = config()
    return {
        "version": 8,
        "name": "Neo Map",
        "sources": {
            "osm": {
                "type": "vector",
                "tiles": [cfg["vector_tiles"]],
                "attribution": cfg["attribution"],
            },
            "satellite": {
                "type": "raster",
                "tiles": [cfg["satellite_tiles"]],
                "tileSize": 256,
                "attribution": cfg["attribution"],
            },
        },
        "layers": [
            # Base OSM (visible by default)
            {"id": "bg", "type": "background", "paint": {"background-color": "#0b1220"}},
            # Satellite raster (toggled by UI)
            {"id": "satellite", "type": "raster", "source": "satellite",
             "layout": {"visibility": "none"},
             "paint": {"raster-opacity": 1.0}},
            # Vector layers on top — a compact subset
            {"id": "water", "type": "fill", "source": "osm", "source-layer": "water",
             "paint": {"fill-color": "#1e3a8a"}},
            {"id": "landuse", "type": "fill", "source": "osm", "source-layer": "landuse",
             "paint": {"fill-color": "#1e293b", "fill-opacity": 0.4}},
            {"id": "roads", "type": "line", "source": "osm", "source-layer": "transportation",
             "paint": {"line-color": "#64748b", "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.5, 16, 4]}},
            {"id": "buildings", "type": "fill", "source": "osm", "source-layer": "building",
             "minzoom": 14, "paint": {"fill-color": "#334155", "fill-opacity": 0.6}},
            {"id": "place-labels", "type": "symbol", "source": "osm", "source-layer": "place",
             "layout": {"text-field": ["get", "name"], "text-size": 12},
             "paint": {"text-color": "#e2e8f0", "text-halo-color": "#0b1220", "text-halo-width": 1}},
        ],
    }
'''

(root / "core" / "geo" / "tiles.py").write_text(tiles, encoding="utf-8")
print("[ok] core/geo/tiles.py")

# ============================================================
# core/geo/satellite.py — satellite analysis (Prithvi-ready stub)
# ============================================================
satellite = r'''"""Satellite analysis — Prithvi-EO-2.0 / Clay hooks.

The heavy models (Prithvi-EO-2.0, Clay, Satlas) need a GPU with >=16GB VRAM
to run at practical speed. On CPU-only machines they take minutes per tile.
So this module:

  * Serves the free EOX Sentinel-2 cloudless tiles as a visible layer
  * Provides a `analyze_polygon()` function that will, once the models are
    installed, run Prithvi-EO-2.0 inference on the polygon's satellite crop
  * Falls back gracefully with an "insufficient hardware" message today

To enable Prithvi inference, install:
    pip install terratorch
    huggingface-cli download ibm-nasa-geospatial/Prithvi-EO-2.0-300M \\
        --local-dir models/prithvi-eo-2.0

Then set NEO_GEOSPATIAL_MODEL=prithvi-eo-2.0 in .env.
"""
from __future__ import annotations
import os
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger("geo.satellite")

MODEL_ENV = os.getenv("NEO_GEOSPATIAL_MODEL", "").strip()   # "" | "prithvi-eo-2.0"


def status() -> Dict[str, Any]:
    """Report which satellite analysis backends are available."""
    info = {
        "tile_layer": "eox-sentinel-2-cloudless-2024",
        "model_configured": MODEL_ENV or None,
        "model_loaded": False,
        "hardware_ok": _has_gpu(),
    }

    if MODEL_ENV == "prithvi-eo-2.0":
        try:
            import terratorch  # noqa: F401
            info["terratorch_installed"] = True
        except ImportError:
            info["terratorch_installed"] = False
            info["hint"] = "pip install terratorch"
    return info


def _has_gpu() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def analyze_polygon(geojson: Dict[str, Any], task: str = "landcover") -> Dict[str, Any]:
    """Run a geospatial foundation model over a polygon.

    task: "landcover" | "burn_scar" | "crop_health" | "flood"

    Returns a dict with results. On CPU-only hardware, returns a
    structured "insufficient_hardware" response rather than crashing.
    """
    if not _has_gpu():
        return {
            "ok": False,
            "reason": "no_gpu",
            "message": (
                "Prithvi-EO-2.0 and Clay require a CUDA GPU with >=16GB VRAM "
                "for practical inference. This machine has no GPU. "
                "The satellite imagery layer still works — this only affects "
                "on-demand analysis of specific polygons."
            ),
            "alternative": (
                "Use the satellite tile layer visually, or run analysis on a "
                "GPU machine and POST results back to /api/geo/observations."
            ),
        }

    if MODEL_ENV != "prithvi-eo-2.0":
        return {
            "ok": False,
            "reason": "model_not_configured",
            "message": "Set NEO_GEOSPATIAL_MODEL=prithvi-eo-2.0 in .env to enable.",
        }

    try:
        # Real Prithvi inference path — only reached on GPU machines
        from core.geo.prithvi import run_inference
        return run_inference(geojson, task=task)
    except ImportError:
        return {
            "ok": False,
            "reason": "prithvi_module_missing",
            "message": "core/geo/prithvi.py not installed. See docs/GEOSPATIAL.md.",
        }
'''

(root / "core" / "geo" / "satellite.py").write_text(satellite, encoding="utf-8")
print("[ok] core/geo/satellite.py")

# ============================================================
# core/geo/cameras.py — camera integration adapter
# ============================================================
cameras = r'''"""Camera integration — Frigate NVR, RTSP, ONVIF.

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
'''

(root / "core" / "geo" / "cameras.py").write_text(cameras, encoding="utf-8")
print("[ok] core/geo/cameras.py")

# ============================================================
# map_ui.py — /map page + /api/geo/* routes
# ============================================================
map_ui = r'''"""Map UI — self-hosted Google-Maps-comparable page at /map.

Uses MapLibre GL JS (open source) + Terra Draw for boundary drawing.
"""
from __future__ import annotations
import json
import logging
from flask import Response, jsonify, request

from core.geo import store, tiles, satellite, cameras

log = logging.getLogger("map_ui")


PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<title>Neo Map</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script src="https://unpkg.com/@terraformer/wkt@2.2.1/dist/terraformer.js"></script>
<script src="https://unpkg.com/terra-draw@1.0.0/dist/terra-draw.umd.js"></script>
<style>
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
       background:#0b1220;color:#e2e8f0;}
  #map{position:absolute;top:0;bottom:0;left:0;right:320px;}
  #side{position:absolute;top:0;bottom:0;right:0;width:320px;
        background:#0f172a;border-left:1px solid #1e293b;overflow-y:auto;padding:14px;}
  h2{margin:0 0 8px 0;font-size:15px;}
  .row{display:flex;gap:6px;margin-bottom:8px;}
  button{background:#1d4ed8;color:#fff;border:none;padding:6px 10px;
         border-radius:6px;cursor:pointer;font-size:12px;}
  button:hover{background:#2563eb;}
  button.ghost{background:#334155;}
  button.ghost:hover{background:#475569;}
  button.danger{background:#7f1d1d;}
  button.danger:hover{background:#991b1b;}
  .list{max-height:280px;overflow-y:auto;font-size:12px;}
  .list .item{padding:8px;border-bottom:1px solid #1e293b;cursor:pointer;}
  .list .item:hover{background:#1e293b;}
  .item .meta{color:#64748b;font-size:10px;margin-top:3px;}
  input,select,textarea{width:100%;background:#0b1220;color:#e2e8f0;border:1px solid #334155;
                        border-radius:6px;padding:5px 8px;font-size:12px;box-sizing:border-box;
                        margin-bottom:6px;}
  label{display:block;color:#94a3b8;font-size:11px;margin-bottom:2px;}
  .badge{display:inline-block;padding:1px 6px;border-radius:999px;font-size:10px;
         background:#1e293b;color:#94a3b8;margin-left:4px;}
  .coord{font-family:monospace;font-size:10px;color:#64748b;}
</style></head>
<body>
<div id="map"></div>
<div id="side">
  <h2>🗺️ Neo Map</h2>
  <div class="row">
    <button id="btn-sat" class="ghost">Satellite</button>
    <button id="btn-draw" class="ghost">Draw</button>
    <button id="btn-save" disabled>Save</button>
  </div>

  <label>Properties</label>
  <div class="list" id="prop-list"></div>
  <div class="row">
    <button id="btn-new-prop" class="ghost">+ New property</button>
  </div>

  <label>Cameras</label>
  <div class="list" id="cam-list"></div>
  <div class="row">
    <button id="btn-new-cam" class="ghost">+ Add camera</button>
  </div>

  <label>Recent observations</label>
  <div class="list" id="obs-list"></div>

  <div style="margin-top:12px;color:#475569;font-size:10px;" id="status">
    loading…
  </div>
</div>

<script>
const map = new maplibregl.Map({
  container: 'map',
  style: 'STYLE_URL_PLACEHOLDER',
  center: [36.8219, -1.2921],   // Nairobi
  zoom: 8,
  hash: true
});
map.addControl(new maplibregl.NavigationControl(), 'top-left');
map.addControl(new maplibregl.ScaleControl({unit: 'metric'}), 'bottom-left');

let satelliteOn = false;
let draw = null;
let pendingPolygon = null;

map.on('load', async () => {
  // ---- property boundaries as a GeoJSON source ----
  map.addSource('properties', {type: 'geojson', data: {type:'FeatureCollection', features: []}});
  map.addLayer({id: 'prop-fill', type: 'fill', source: 'properties',
    paint: {'fill-color': '#3b82f6', 'fill-opacity': 0.25}});
  map.addLayer({id: 'prop-line', type: 'line', source: 'properties',
    paint: {'line-color': '#60a5fa', 'line-width': 2}});

  // ---- camera markers ----
  map.addSource('cameras', {type: 'geojson', data: {type:'FeatureCollection', features: []}});
  map.addLayer({id: 'cam-dots', type: 'circle', source: 'cameras',
    paint: {'circle-radius': 7, 'circle-color': '#ef4444',
            'circle-stroke-color': '#fff', 'circle-stroke-width': 2}});

  // ---- observations ----
  map.addSource('observations', {type: 'geojson', data: {type:'FeatureCollection', features: []}});
  map.addLayer({id: 'obs-dots', type: 'circle', source: 'observations',
    paint: {'circle-radius': 4, 'circle-color': '#f59e0b', 'circle-opacity': 0.7}});

  await Promise.all([refreshProperties(), refreshCameras(), refreshObservations()]);
  setStatus('ready');
});

function setStatus(t){ document.getElementById('status').textContent = t; }

async function refreshProperties(){
  const r = await fetch('/api/geo/properties');
  const j = await r.json();
  renderPropList(j.properties);

  const features = [];
  for (const p of j.properties) {
    const detail = await (await fetch('/api/geo/properties/' + p.id)).json();
    for (const b of (detail.boundaries || [])) {
      features.push({
        type: 'Feature',
        properties: {id: p.id, name: p.name, kind: p.kind},
        geometry: b.geojson
      });
    }
  }
  map.getSource('properties').setData({type:'FeatureCollection', features});
}

function renderPropList(properties){
  const box = document.getElementById('prop-list');
  if (!properties.length){ box.innerHTML = '<div class="item" style="color:#475569">none yet — click Draw, then Save</div>'; return; }
  box.innerHTML = properties.map(p => `
    <div class="item" onclick="focusProperty('${p.id}', ${p.center_lat ?? 'null'}, ${p.center_lng ?? 'null'})">
      <div>${escapeHtml(p.name)} <span class="badge">${p.kind}</span></div>
      <div class="meta">${p.area_m2 ? (p.area_m2/10000).toFixed(3) + ' ha' : '—'} · ${p.boundary_count} boundary</div>
    </div>`).join('');
}

async function refreshCameras(){
  const r = await fetch('/api/geo/cameras');
  const j = await r.json();
  document.getElementById('cam-list').innerHTML = j.cameras.length
    ? j.cameras.map(c => `<div class="item">
        <div>${escapeHtml(c.name)} <span class="badge">${c.kind}</span></div>
        <div class="meta">${c.endpoint}</div></div>`).join('')
    : '<div class="item" style="color:#475569">none yet</div>';
  const features = j.cameras.filter(c => c.lat && c.lng).map(c => ({
    type: 'Feature', properties: {name: c.name},
    geometry: {type:'Point', coordinates: [c.lng, c.lat]}
  }));
  map.getSource('cameras').setData({type:'FeatureCollection', features});
}

async function refreshObservations(){
  const r = await fetch('/api/geo/observations?limit=50');
  const j = await r.json();
  document.getElementById('obs-list').innerHTML = j.observations.length
    ? j.observations.slice(0,20).map(o => `<div class="item">
        <div>${o.kind} <span class="badge">${o.source}</span></div>
        <div class="meta">${new Date((o.ts||0)*1000).toLocaleTimeString()} · conf ${(o.confidence*100).toFixed(0)}%</div>
      </div>`).join('')
    : '<div class="item" style="color:#475569">none yet</div>';
  const features = j.observations.filter(o => o.lat && o.lng).map(o => ({
    type: 'Feature', properties: {kind: o.kind},
    geometry: {type:'Point', coordinates: [o.lng, o.lat]}
  }));
  map.getSource('observations').setData({type:'FeatureCollection', features});
}

function focusProperty(id, lat, lng){
  if (lat != null && lng != null) map.flyTo({center: [lng, lat], zoom: 16});
}

// ---- satellite toggle ----
document.getElementById('btn-sat').onclick = () => {
  satelliteOn = !satelliteOn;
  map.setLayoutProperty('satellite', 'visibility', satelliteOn ? 'visible' : 'none');
  document.getElementById('btn-sat').classList.toggle('ghost', !satelliteOn);
};

// ---- draw mode ----
document.getElementById('btn-draw').onclick = () => {
  if (draw) { draw.stop(); draw = null; setStatus('draw off'); document.getElementById('btn-save').disabled = true; return; }
  draw = new TerraDraw.TerraDraw({
    adapter: new TerraDraw.TerraDrawMapLibreGLAdapter({ map, lib: maplibregl }),
    modes: [new TerraDraw.TerraDrawPolygonMode()],
  });
  draw.start();
  draw.setMode('polygon');
  draw.on('finish', (id) => {
    pendingPolygon = draw.getSnapshot().find(f => f.id === id);
    document.getElementById('btn-save').disabled = false;
    setStatus('polygon ready — click Save');
  });
  setStatus('draw on — click to add vertices, double-click to close');
};

document.getElementById('btn-save').onclick = async () => {
  if (!pendingPolygon) return;
  const name = prompt('Property name:', 'My farm');
  if (!name) return;
  const kind = prompt('Kind (farm|house|plot|building|other):', 'farm') || 'farm';
  let pid = await (await fetch('/api/geo/properties', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, kind})
  })).json();
  pid = pid.property.id;
  await fetch('/api/geo/properties/' + pid + '/boundaries', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({geojson: pendingPolygon.geometry})
  });
  if (draw) { draw.stop(); draw = null; }
  document.getElementById('btn-save').disabled = true;
  pendingPolygon = null;
  await refreshProperties();
  setStatus('saved');
};

document.getElementById('btn-new-prop').onclick = () => {
  document.getElementById('btn-draw').click();
};

document.getElementById('btn-new-cam').onclick = async () => {
  const name = prompt('Camera name:'); if(!name) return;
  const endpoint = prompt('Endpoint (rtsp://... or frigate cam name):', 'rtsp://');
  if(!endpoint) return;
  const lat = parseFloat(prompt('Latitude (optional):', '') || '');
  const lng = parseFloat(prompt('Longitude (optional):', '') || '');
  await fetch('/api/geo/cameras', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, kind: endpoint.startsWith('rtsp') ? 'rtsp' : 'frigate',
                          endpoint, lat: isNaN(lat)?null:lat, lng: isNaN(lng)?null:lng})
  });
  refreshCameras();
};

function escapeHtml(s){ return (s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

setInterval(refreshObservations, 30000);
</script>
</body></html>"""


def register_map_routes(app, agent_core=None):
    # ---------- page ----------
    @app.route("/map")
    def _map_page():
        style = tiles.map_style()
        # embed style inline (MapLibre accepts a style object)
        html = PAGE.replace("'STYLE_URL_PLACEHOLDER'", json.dumps(style))
        return Response(html, mimetype="text/html")

    # ---------- style ----------
    @app.route("/api/geo/style")
    def _style():
        return jsonify(tiles.map_style())

    @app.route("/api/geo/tile-config")
    def _tile_config():
        return jsonify(tiles.config())

    # ---------- properties ----------
    @app.route("/api/geo/properties", methods=["GET", "POST"])
    def _properties():
        if request.method == "POST":
            data = request.get_json() or {}
            name = (data.get("name") or "").strip()
            if not name:
                return jsonify({"error": "name required"}), 400
            p = store.add_property(
                name=name,
                kind=(data.get("kind") or "other"),
                lat=data.get("lat"), lng=data.get("lng"),
                notes=data.get("notes", ""),
                tags=data.get("tags") or [],
            )
            return jsonify({"property": p})
        return jsonify({"properties": store.list_properties()})

    @app.route("/api/geo/properties/<pid>", methods=["GET", "DELETE"])
    def _property(pid):
        if request.method == "DELETE":
            ok = store.delete_property(pid)
            return jsonify({"ok": ok})
        p = store.get_property(pid)
        if not p:
            return jsonify({"error": "not found"}), 404
        return jsonify(p)

    @app.route("/api/geo/properties/<pid>/boundaries", methods=["POST"])
    def _add_boundary(pid):
        data = request.get_json() or {}
        gj = data.get("geojson")
        if not gj or gj.get("type") != "Polygon":
            return jsonify({"error": "geojson Polygon required"}), 400
        b = store.add_boundary(pid, gj, label=data.get("label", ""))
        return jsonify({"boundary": b})

    @app.route("/api/geo/boundaries/<bid>", methods=["DELETE"])
    def _del_boundary(bid):
        return jsonify({"ok": store.delete_boundary(bid)})

    # ---------- cameras ----------
    @app.route("/api/geo/cameras", methods=["GET", "POST"])
    def _cameras():
        if request.method == "POST":
            data = request.get_json() or {}
            c = store.add_camera(
                name=data.get("name", "camera"),
                kind=data.get("kind", "rtsp"),
                endpoint=data.get("endpoint", ""),
                lat=data.get("lat"), lng=data.get("lng"),
                facing_deg=data.get("facing_deg"),
                notes=data.get("notes", ""),
            )
            return jsonify({"camera": c})
        return jsonify({"cameras": store.list_cameras(),
                        "frigate": cameras.frigate_status()})

    @app.route("/api/geo/cameras/<cid>", methods=["DELETE"])
    def _del_camera(cid):
        return jsonify({"ok": store.delete_camera(cid)})

    @app.route("/api/geo/cameras/sync", methods=["POST"])
    def _sync_cams():
        return jsonify(cameras.sync_frigate_observations())

    # ---------- observations ----------
    @app.route("/api/geo/observations", methods=["GET", "POST"])
    def _obs():
        if request.method == "POST":
            data = request.get_json() or {}
            o = store.add_observation(
                source=data.get("source", "manual"),
                kind=data.get("kind", "unknown"),
                confidence=float(data.get("confidence", 0.0)),
                lat=float(data.get("lat", 0.0)),
                lng=float(data.get("lng", 0.0)),
                camera_id=data.get("camera_id"),
                payload=data.get("payload") or {},
            )
            return jsonify({"observation": o})
        limit = int(request.args.get("limit", 100))
        return jsonify({"observations": store.recent_observations(limit=limit)})

    # ---------- satellite ----------
    @app.route("/api/geo/satellite/status")
    def _sat_status():
        return jsonify(satellite.status())

    @app.route("/api/geo/satellite/analyze", methods=["POST"])
    def _sat_analyze():
        data = request.get_json() or {}
        gj = data.get("geojson")
        task = data.get("task", "landcover")
        if not gj:
            return jsonify({"error": "geojson required"}), 400
        return jsonify(satellite.analyze_polygon(gj, task=task))

    log.info("[MapUI] routes registered at /map")
'''

(root / "map_ui.py").write_text(map_ui, encoding="utf-8")
print("[ok] map_ui.py")

# ============================================================
# Patch launcher.py — register map routes
# ============================================================
lp = root / "launcher.py"
src = lp.read_text(encoding="utf-8")

anchor = (
    '            from scheduler_ui import register_scheduler_routes\n'
    '            register_scheduler_routes(self.app, agent_core=self.agent_core)\n'
    '        except Exception as e:\n'
    '            logger.warning(f"[Neo] scheduler UI not registered: {e}")'
)
insert = anchor + '''

        # ═══ REGISTER MAP UI (NEW) ═══
        try:
            from map_ui import register_map_routes
            register_map_routes(self.app, agent_core=self.agent_core)
            logger.info("[Neo] Map UI routes registered at /map")
        except Exception as e:
            logger.warning(f"[Neo] map UI not registered: {e}")
'''
if anchor in src:
    src = src.replace(anchor, insert, 1)
    print("[ok] registered /map routes in launcher")
elif "register_map_routes" in src:
    print("[skip] launcher already has map routes")
else:
    print("[warn] scheduler UI anchor not found — manual edit needed")

lp.write_text(src, encoding="utf-8")

# ---------- sanity ----------
import py_compile
for p in [
    root/"core"/"geo"/"store.py",
    root/"core"/"geo"/"tiles.py",
    root/"core"/"geo"/"satellite.py",
    root/"core"/"geo"/"cameras.py",
    root/"map_ui.py",
    root/"launcher.py",
]:
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"[ok] {p.relative_to(root)} compiles")
    except py_compile.PyCompileError as e:
        print(f"[fail] {p.relative_to(root)}: {e}")
        raise SystemExit(1)

print()
print("Layer 1 (Location) installed. Restart launcher and open:")
print("  http://127.0.0.1:8000/map")
print()
print("What works right now:")
print("  - Self-hosted map with OSM vector tiles (Google-Maps-look)")
print("  - Satellite toggle (Sentinel-2 cloudless, no signup)")
print("  - Draw a farm/property boundary, save it, it persists")
print("  - Camera markers (add RTSP or Frigate endpoints)")
print("  - Observations table + polling")
print("  - /api/geo/satellite/analyze reports GPU status (won't run models on this box)")