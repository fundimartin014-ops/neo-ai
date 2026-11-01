from pathlib import Path

content = '''"""Kenyan town/city coordinates for the farm brief and weather lookups."""
from __future__ import annotations

from typing import Optional

# name -> (latitude, longitude, display name)
TOWNS: dict[str, tuple[float, float, str]] = {
    "nakuru":     (-0.3031, 36.0800, "Nakuru"),
    "nairobi":    (-1.2921, 36.8219, "Nairobi"),
    "eldoret":    (0.5143, 35.2698, "Eldoret"),
    "kisumu":     (-0.0917, 34.7680, "Kisumu"),
    "mombasa":    (-4.0435, 39.6682, "Mombasa"),
    "nyeri":      (-0.4169, 36.9514, "Nyeri"),
    "meru":       (0.0515, 37.6456, "Meru"),
    "thika":      (-1.0333, 37.0693, "Thika"),
    "kitale":     (1.0157, 35.0062, "Kitale"),
    "kericho":    (-0.3689, 35.2863, "Kericho"),
    "kakamega":   (0.2827, 34.7519, "Kakamega"),
    "machakos":   (-1.5177, 37.2634, "Machakos"),
    "naivasha":   (-0.7167, 36.4359, "Naivasha"),
    "bungoma":    (0.5635, 34.5606, "Bungoma"),
    "embu":       (-0.5310, 37.4500, "Embu"),
    "garissa":    (-0.4536, 39.6461, "Garissa"),
    "malindi":    (-3.2192, 40.1169, "Malindi"),
    "kitui":      (-1.3667, 38.0167, "Kitui"),
    "narok":      (-1.0833, 35.8667, "Narok"),
    "kiambu":     (-1.1714, 36.8356, "Kiambu"),
    "muranga":    (-0.7167, 37.1500, "Murang'a"),
    "murang'a":   (-0.7167, 37.1500, "Murang'a"),
    "voi":        (-3.3961, 38.5561, "Voi"),
    "kilifi":     (-3.6305, 39.8499, "Kilifi"),
    "lamu":       (-2.2717, 40.9020, "Lamu"),
    "isiolo":     (0.3546, 37.5822, "Isiolo"),
    "kajiado":    (-1.8500, 36.7833, "Kajiado"),
    "trans nzoia":(1.0559, 34.9500, "Trans Nzoia"),
}


def resolve_location(name: str) -> Optional[tuple[float, float, str]]:
    """Return (lat, lon, display_name) for a name, or None if unknown."""
    if not name:
        return None
    key = name.strip().lower()
    if key in TOWNS:
        return TOWNS[key]
    # Try word-boundary fallback
    for known, coords in TOWNS.items():
        if known in key or key in known:
            return coords
    return None


def known_towns() -> list[str]:
    """Sorted, deduped display names of all supported towns."""
    return sorted({v[2] for v in TOWNS.values()})
'''

Path("agents/locations.py").write_text(content, encoding="utf-8")
print("Created agents/locations.py")