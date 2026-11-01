"""Satellite analysis — Prithvi-EO-2.0 / Clay hooks.

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
            "No geospatial backend available. Enable one of:\n"
            "  * HF_TOKEN        → huggingface.co/join (free, no card)\n"
            "  * REPLICATE_API_TOKEN → replicate.com/signin (free trial credits)\n"
            "  * or install a local GPU + Prithvi-EO-2.0"
        ),
        "errors": cloud_errors,
    }
