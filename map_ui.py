"""Map UI — self-hosted Google-Maps-comparable page at /map.

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

    # ---------- cloud backend status ----------
    @app.route("/api/geo/backends")
    def _backends():
        from core.geo import cloud as cloud_geo
        from core.vision import cloud_detect
        return jsonify({
            "geospatial": cloud_geo.status(),
            "vision": cloud_detect.status(),
        })

    # ---------- cloud vision detect ----------
    @app.route("/api/vision/cloud-detect", methods=["POST"])
    def _cloud_detect():
        from core.vision import cloud_detect
        data = request.get_json(silent=True) or {}
        path = data.get("path")
        url = data.get("url")
        prompt = data.get("prompt")
        lat = data.get("lat"); lng = data.get("lng")
        if path:
            return jsonify(cloud_detect.detect_file(path, prompt=prompt, lat=lat, lng=lng))
        if url:
            return jsonify(cloud_detect.detect_url(url, prompt=prompt, lat=lat, lng=lng))
        return jsonify({"error": "provide path or url"}), 400

    log.info("[MapUI] routes registered at /map")
