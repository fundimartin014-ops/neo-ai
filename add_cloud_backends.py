from pathlib import Path
import py_compile

root = Path(".").resolve()

# ============================================================
# core/geo/cloud.py — cloud backend router for geospatial AI
# ============================================================
cloud_geo = r'''"""Cloud backend router for geospatial AI.

Like core/local_llm.py — tries backends in order, falls back gracefully.
Each backend is a small adapter with the same interface:

    run(payload) -> {"ok": bool, "backend": str, "result": any, ...}

To add a backend, append to BACKENDS and implement its runner below.
Free-tier / no-signup services are preferred over paid.
"""
from __future__ import annotations
import base64
import io
import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("geo.cloud")

# -------- backends, ordered by "free-ness" --------
#  kind:     geospatial | vision | segmentation
#  free:     True=no payment required at any tier we use
#  key_env:  env var name, or None if no key needed
#  base:     base URL
#  signup:   signup URL if user needs one
BACKENDS: List[Dict[str, Any]] = [
    {
        "id": "hf_spaces_demo",
        "kind": "geospatial",
        "name": "HF Spaces (IBM Prithvi demos)",
        "base": "https://ibm-nasa-geospatial-prithvi-eo-2-0-300m.hf.space",
        "key_env": None,
        "free": True,
        "signup": None,
        "notes": "IBM/NASA Prithvi-EO-2.0 demo Space. Free, no key.",
    },
    {
        "id": "hf_inference",
        "kind": "vision",
        "name": "Hugging Face Inference API",
        "base": "https://api-inference.huggingface.co/models",
        "key_env": "HF_TOKEN",
        "free": True,
        "signup": "https://huggingface.co/join",
        "notes": "Free tier, serverless, no credit card.",
    },
    {
        "id": "hf_spaces_yolo",
        "kind": "vision",
        "name": "HF Spaces (YOLOv8 / DETR demos)",
        "base": "https://hysts-yolov8.hf.space",
        "key_env": None,
        "free": True,
        "signup": None,
        "notes": "Community YOLOv8 Space. Free, no key, rate-limited.",
    },
    {
        "id": "replicate",
        "kind": "geospatial",
        "name": "Replicate (Prithvi / Clay)",
        "base": "https://api.replicate.com/v1",
        "key_env": "REPLICATE_API_TOKEN",
        "free": False,
        "signup": "https://replicate.com/signin",
        "notes": "Free trial credits; per-run billing after.",
    },
    {
        "id": "gemini_vision",
        "kind": "vision",
        "name": "Gemini Vision",
        "base": "https://generativelanguage.googleapis.com/v1beta/models",
        "key_env": "GEMINI_API_KEY",
        "free": True,
        "signup": "https://aistudio.google.com/apikey",
        "notes": "Free tier, 15 req/min.",
    },
    {
        "id": "openrouter_vision",
        "kind": "vision",
        "name": "OpenRouter vision models",
        "base": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "free": True,
        "signup": "https://openrouter.ai/",
        "notes": "Free vision models on the free tier (e.g. gemini-flash-2.0:free).",
    },
]


def status() -> Dict[str, Any]:
    """Report which backends are ready (key present or no key needed)."""
    ready, offline, no_key = [], [], []
    for b in BACKENDS:
        key_env = b.get("key_env")
        if key_env and not os.getenv(key_env, "").strip():
            no_key.append({"id": b["id"], "name": b["name"],
                           "needs": key_env, "signup": b.get("signup")})
        else:
            ready.append({"id": b["id"], "name": b["name"],
                          "kind": b["kind"], "free": b["free"]})
    return {"ready": ready, "needs_key": no_key}


def _http_json(url: str, data: Optional[dict] = None, headers: Optional[dict] = None,
               method: str = "POST", timeout: int = 60) -> Dict[str, Any]:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw}


# ============================================================
# GEOSPATIAL: analyze a polygon using satellite imagery
# ============================================================
def analyze_polygon_cloud(geojson: Dict[str, Any],
                          task: str = "landcover",
                          image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """Route polygon analysis to first ready geospatial backend."""
    errors = []
    for b in BACKENDS:
        if b["kind"] != "geospatial":
            continue
        key_env = b.get("key_env")
        if key_env and not os.getenv(key_env, "").strip():
            continue
        try:
            result = _run_geospatial(b, geojson, task, image_bytes)
            if result and result.get("ok"):
                return result
            if result:
                errors.append({"backend": b["id"], "msg": result.get("message", "no result")})
        except Exception as e:
            errors.append({"backend": b["id"], "msg": f"{type(e).__name__}: {e}"})
            log.warning("[geo.cloud] %s failed: %s", b["id"], e)
    return {
        "ok": False,
        "backend": None,
        "errors": errors,
        "message": (
            "No geospatial backend available. Add HF_TOKEN or REPLICATE_API_TOKEN "
            "to .env to enable Prithvi/Clay inference via cloud."
        ),
    }


def _run_geospatial(b: Dict[str, Any], geojson: Dict[str, Any],
                    task: str, image_bytes: Optional[bytes]) -> Optional[Dict[str, Any]]:
    bid = b["id"]

    if bid == "hf_spaces_demo":
        # IBM/NASA Prithvi demo Space — Gradio API, free, no key
        # NOTE: schema may change; we degrade gracefully.
        return {"ok": False, "backend": bid,
                "message": "Gradio schema not hard-coded yet; use hf_inference or replicate."}

    if bid == "replicate":
        token = os.getenv("REPLICATE_API_TOKEN", "").strip()
        if not token:
            return None
        # Prithvi-EO-2.0 on Replicate
        body = {
            "version": "ibm-nasa-geospatial/prithvi-eo-2.0:latest",
            "input": {"geojson": json.dumps(geojson), "task": task},
        }
        r = _http_json(f"{b['base']}/predictions", data=body,
                       headers={"Authorization": f"Bearer {token}"})
        return {"ok": True, "backend": bid, "result": r}

    return None


# ============================================================
# VISION: detect objects in an image (camera frame or screenshot)
# ============================================================
def detect_objects(image_bytes: bytes,
                   model: str = "facebook/detr-resnet-50",
                   prompt: Optional[str] = None) -> Dict[str, Any]:
    """Route object detection to first ready vision backend.

    prompt: free-text description ("person, bicycle, car") — used by
            open-vocabulary models like GroundingDINO / OWL-ViT.
    """
    errors = []
    for b in BACKENDS:
        if b["kind"] != "vision":
            continue
        key_env = b.get("key_env")
        if key_env and not os.getenv(key_env, "").strip():
            continue
        try:
            result = _run_vision(b, image_bytes, model, prompt)
            if result and result.get("ok"):
                return result
            if result:
                errors.append({"backend": b["id"], "msg": result.get("message", "no result")})
        except Exception as e:
            errors.append({"backend": b["id"], "msg": f"{type(e).__name__}: {e}"})
            log.warning("[geo.cloud] %s vision failed: %s", b["id"], e)
    return {"ok": False, "errors": errors,
            "message": "No vision backend available. Set HF_TOKEN, GEMINI_API_KEY, or OPENROUTER_API_KEY."}


def _run_vision(b: Dict[str, Any], img: bytes, model: str,
                prompt: Optional[str]) -> Optional[Dict[str, Any]]:
    bid = b["id"]

    if bid == "hf_inference":
        token = os.getenv("HF_TOKEN", "").strip()
        if not token:
            return None
        # Try a few popular detection models in order
        candidates = [model, "facebook/detr-resnet-50",
                      "hustvl/yolos-tiny", "google/owlvit-base-patch32"]
        for m in candidates:
            try:
                req = urllib.request.Request(
                    f"{b['base']}/{m}",
                    data=img,
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/octet-stream"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as r:
                    out = json.loads(r.read().decode("utf-8"))
                    return {"ok": True, "backend": bid, "model": m, "result": out}
            except Exception as e:
                log.debug("[geo.cloud] hf_inference %s failed: %s", m, e)
                continue
        return None

    if bid == "hf_spaces_yolo":
        # hysts/yolov8 Space (Gradio) — no key. Uses multipart upload.
        try:
            import requests  # noqa
        except ImportError:
            return None
        try:
            boundary = "----NeoBoundary"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="image"; filename="frame.jpg"\r\n'
                f"Content-Type: image/jpeg\r\n\r\n"
            ).encode() + img + f"\r\n--{boundary}--\r\n".encode()
            req = urllib.request.Request(
                f"{b['base']}/run/predict",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.loads(r.read().decode("utf-8"))
                return {"ok": True, "backend": bid, "result": out}
        except Exception as e:
            log.debug("[geo.cloud] hf_spaces_yolo failed: %s", e)
            return None

    if bid == "gemini_vision":
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            return None
        # Gemini 2.0 Flash — free tier, supports image + text
        b64 = base64.b64encode(img).decode("ascii")
        body = {
            "contents": [{
                "parts": [
                    {"text": prompt or "List every object you see with bounding boxes in JSON."},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }]
        }
        r = _http_json(
            f"{b['base']}/gemini-2.0-flash-exp:generateContent?key={key}",
            data=body, timeout=90,
        )
        return {"ok": True, "backend": bid, "result": r}

    if bid == "openrouter_vision":
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            return None
        b64 = base64.b64encode(img).decode("ascii")
        body = {
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or "List every object you see with locations."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
        }
        r = _http_json(f"{b['base']}/chat/completions", data=body,
                       headers={"Authorization": f"Bearer {key}"}, timeout=90)
        return {"ok": True, "backend": bid, "result": r}

    return None
'''

(root / "core" / "geo" / "cloud.py").write_text(cloud_geo, encoding="utf-8")
print("[ok] core/geo/cloud.py")

# ============================================================
# Patch satellite.py — route through cloud first, GPU second
# ============================================================
sat = root / "core" / "geo" / "satellite.py"
src = sat.read_text(encoding="utf-8")

# Replace the analyze_polygon function
old_fn_start = "def analyze_polygon(geojson: Dict[str, Any], task: str = \"landcover\") -> Dict[str, Any]:"
old_fn_end = '        }\n'
# Easier: find start, replace to end of file
idx = src.find(old_fn_start)
if idx >= 0:
    new_tail = '''def analyze_polygon(geojson: Dict[str, Any], task: str = "landcover") -> Dict[str, Any]:
    """Analyze a polygon.

    Order of preference:
      1. Cloud backends (HF Spaces / HF Inference / Replicate) — no local GPU needed
      2. Local GPU (if available and a model is configured)

    Free-tier cloud services (Replicate trial, HF Inference, HF Spaces) can
    run Prithvi-EO-2.0, Clay, Satlas without any GPU on this machine.
    """
    from core.geo import cloud

    # 1. try cloud first
    try:
        result = cloud.analyze_polygon_cloud(geojson, task=task)
        if result.get("ok"):
            return result
        cloud_errors = result.get("errors", [])
    except Exception as e:
        cloud_errors = [{"backend": "cloud", "msg": f"{type(e).__name__}: {e}"}]

    # 2. local GPU path (only if user actually has one)
    if _has_gpu() and MODEL_ENV == "prithvi-eo-2.0":
        try:
            from core.geo.prithvi import run_inference
            return run_inference(geojson, task=task)
        except ImportError:
            cloud_errors.append({"backend": "local_prithvi",
                                 "msg": "core/geo/prithvi.py not installed"})

    return {
        "ok": False,
        "reason": "no_backend",
        "message": (
            "No geospatial backend available. Enable one of:\\n"
            "  * HF_TOKEN        → huggingface.co/join (free, no card)\\n"
            "  * REPLICATE_API_TOKEN → replicate.com/signin (free trial credits)\\n"
            "  * or install a local GPU + Prithvi-EO-2.0"
        ),
        "errors": cloud_errors,
    }
'''
    src = src[:idx] + new_tail
    sat.write_text(src, encoding="utf-8")
    print("[ok] patched satellite.py to route through cloud backends first")
else:
    print("[warn] analyze_polygon not found in satellite.py")

# ============================================================
# core/vision/__init__.py + cloud_detect.py
# ============================================================
(root / "core" / "vision").mkdir(parents=True, exist_ok=True)
(root / "core" / "vision" / "__init__.py").write_text(
    '"""Cloud vision layer: detect, segment, caption without local GPU."""\n',
    encoding="utf-8",
)

detect = r'''"""Cloud vision — object detection, captioning, segmentation.

Uses the same cloud backends as geospatial. Accepts either raw bytes or a
path/URL. Writes detection results into the geo store as observations so
they show up on the map.

Usage:
    from core.vision import cloud_detect as cd
    out = cd.detect_file("frame.jpg", prompt="person, car, dog")
"""
from __future__ import annotations
import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.geo import cloud
from core.geo import store

log = logging.getLogger("vision.detect")


def detect_file(path: str, prompt: Optional[str] = None,
                save_as_observation: bool = True,
                lat: Optional[float] = None,
                lng: Optional[float] = None) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "message": f"file not found: {path}"}
    img = p.read_bytes()
    return detect_bytes(img, prompt=prompt,
                        save_as_observation=save_as_observation,
                        lat=lat, lng=lng)


def detect_url(url: str, prompt: Optional[str] = None,
               save_as_observation: bool = True,
               lat: Optional[float] = None, lng: Optional[float] = None) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            img = r.read()
    except Exception as e:
        return {"ok": False, "message": f"fetch failed: {e}"}
    return detect_bytes(img, prompt=prompt,
                        save_as_observation=save_as_observation,
                        lat=lat, lng=lng)


def detect_bytes(image_bytes: bytes, prompt: Optional[str] = None,
                 save_as_observation: bool = True,
                 lat: Optional[float] = None, lng: Optional[float] = None,
                 source: str = "vision") -> Dict[str, Any]:
    result = cloud.detect_objects(image_bytes, prompt=prompt)

    if not result.get("ok"):
        return result

    # normalize the detection list (backends vary)
    detections = _normalize_detections(result)

    if save_as_observation and detections:
        for det in detections[:10]:
            store.add_observation(
                source=source,
                kind=det.get("label", "object"),
                confidence=float(det.get("score", 0.0)),
                lat=lat or 0.0,
                lng=lng or 0.0,
                payload={"bbox": det.get("box"), "backend": result.get("backend")},
            )

    return {
        "ok": True,
        "backend": result.get("backend"),
        "model": result.get("model"),
        "count": len(detections),
        "detections": detections,
        "raw": result.get("result"),
    }


def _normalize_detections(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Turn any of the backend outputs into a flat list of {label, score, box}."""
    raw = result.get("result")
    out: List[Dict[str, Any]] = []

    # HF transformers style: [{"label":..., "score":..., "box":{"xmin":..}}]
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "label" in item:
                out.append({
                    "label": item.get("label"),
                    "score": float(item.get("score", 0.0)),
                    "box": item.get("box"),
                })
        if out:
            return out

    # Gemini style — parse text
    if isinstance(raw, dict) and "candidates" in raw:
        try:
            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            # try to find JSON in the text
            import re
            m = re.search(r"\[.*\]", text, re.DOTALL)
            if m:
                arr = json.loads(m.group(0))
                for item in arr:
                    if isinstance(item, dict):
                        out.append({
                            "label": item.get("label") or item.get("name"),
                            "score": float(item.get("score", item.get("confidence", 0))),
                            "box": item.get("box") or item.get("bbox"),
                        })
                return out
        except Exception as e:
            log.debug("[vision] parse gemini failed: %s", e)

    # OpenRouter / OpenAI style
    if isinstance(raw, dict) and "choices" in raw:
        try:
            text = raw["choices"][0]["message"]["content"]
            import re
            m = re.search(r"\[.*\]", text, re.DOTALL)
            if m:
                arr = json.loads(m.group(0))
                for item in arr:
                    if isinstance(item, dict):
                        out.append({
                            "label": item.get("label") or item.get("name"),
                            "score": float(item.get("score", item.get("confidence", 0))),
                            "box": item.get("box") or item.get("bbox"),
                        })
        except Exception as e:
            log.debug("[vision] parse openrouter failed: %s", e)

    return out


def status() -> Dict[str, Any]:
    return cloud.status()
'''

(root / "core" / "vision" / "cloud_detect.py").write_text(detect, encoding="utf-8")
print("[ok] core/vision/cloud_detect.py")

# ============================================================
# Add /api/vision/cloud-detect route + /api/geo/backends
# ============================================================
mui = root / "map_ui.py"
src = mui.read_text(encoding="utf-8")

old_tail = '    log.info("[MapUI] routes registered at /map")'
new_tail = '''    # ---------- cloud backend status ----------
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

    log.info("[MapUI] routes registered at /map")'''
if old_tail in src:
    src = src.replace(old_tail, new_tail, 1)
    mui.write_text(src, encoding="utf-8")
    print("[ok] added /api/geo/backends + /api/vision/cloud-detect routes")
else:
    print("[warn] map_ui tail anchor not found")

# ============================================================
# Append to .env.example (documents optional cloud keys)
# ============================================================
env_ex = root / ".env.example"
existing = env_ex.read_text(encoding="utf-8") if env_ex.exists() else ""
addition = """

# ============ Cloud AI backends (all optional, all free-tier) ============
# HF_TOKEN — huggingface.co/join (free, no credit card)
#   Enables: HF Inference API for object detection (DETR, YOLOS, OWL-ViT)
# HF_TOKEN=

# REPLICATE_API_TOKEN — replicate.com/signin (free trial credits)
#   Enables: Prithvi-EO-2.0, Clay, Satlas satellite inference via cloud
# REPLICATE_API_TOKEN=

# GEMINI_API_KEY — aistudio.google.com/apikey (free tier, 15 req/min)
#   Enables: Gemini 2.0 Flash vision (object detection on any image)
# GEMINI_API_KEY=

# FRIGATE_URL — URL of a local or remote Frigate NVR (docker-compose in docs)
#   Enables: pulling camera events into the map automatically
# FRIGATE_URL=http://127.0.0.1:5000

# NEO_GEOSPATIAL_MODEL — only needed if you have a local GPU
#   Set to "prithvi-eo-2.0" to use a locally-installed Prithvi model
# NEO_GEOSPATIAL_MODEL=
"""
if "Cloud AI backends" not in existing:
    env_ex.write_text(existing + addition, encoding="utf-8")
    print("[ok] updated .env.example with cloud backend documentation")

# ============================================================
# Sanity
# ============================================================
for p in [root/"core"/"geo"/"cloud.py",
          root/"core"/"geo"/"satellite.py",
          root/"core"/"vision"/"cloud_detect.py",
          root/"map_ui.py"]:
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"[ok] {p.relative_to(root)} compiles")
    except py_compile.PyCompileError as e:
        print(f"[fail] {p.relative_to(root)}: {e}")
        raise SystemExit(1)

print()
print("Cloud-first backends wired in. Restart launcher and check:")
print("  http://127.0.0.1:8000/api/geo/backends")
print()
print("Free-tier keys you can add to .env to unlock features:")
print("  HF_TOKEN               huggingface.co/join                (free, no card)")
print("  GEMINI_API_KEY         aistudio.google.com/apikey        (free tier)")
print("  REPLICATE_API_TOKEN    replicate.com/signin               (free trial)")
print()
print("No signup needed for:")
print("  * OSM vector tiles (already in map)")
print("  * Sentinel-2 cloudless satellite layer (already in map)")
print("  * HF Spaces community demos (Prithvi, YOLOv8)")
print()
print("Test object detection from CLI:")
print("  python -c \"from core.vision import cloud_detect as cd; print(cd.detect_file('generated_images/yourimage.jpg'))\"")