"""Cloud vision — object detection, captioning, segmentation.

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
