"""Tile server configuration — where the map gets its imagery.

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
