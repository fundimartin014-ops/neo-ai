"""Cloud backend router for geospatial AI.

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
