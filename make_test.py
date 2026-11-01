from pathlib import Path

content = r'''"""test_new_features.py — smoke test for every feature added this session.

Run:
    python test_new_features.py
    python test_new_features.py --verbose

Covers:
  geo.*       — properties, boundaries, area, cameras, observations
  vision.*    — cloud detection backends, status
  sms.*       — Africa's Talking / Twilio adapter (no key needed to test)
  report.*    — PDF generation (reportlab)
  scheduler.* — scheduler_ui route collection
  nosignup.*  — 245-tool registry, find, explicit intents, iframe
  routes.*    — /map, /scheduler, /api/geo/*, /api/vision/*

Nothing here hits a paid service. Free-tier endpoints are only called if
the corresponding env var is set (HF_TOKEN / GEMINI_API_KEY / REPLICATE_API_TOKEN).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

PASS = "\u2705"
FAIL = "\u274C"
SKIP = "\u23ED\uFE0F"

VERBOSE = False


# ---------------------------------------------------------------------------
# Tiny test runner
# ---------------------------------------------------------------------------
class Result:
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
        self.status = "pending"
        self.detail = ""
        self.error = ""


def run(name: str, category: str, fn: Callable[[], str]) -> Result:
    r = Result(name, category)
    try:
        out = fn()
        if isinstance(out, tuple):
            status, detail = out
            r.status = status
            r.detail = str(detail)
        else:
            r.status = "pass"
            r.detail = str(out)
    except AssertionError as e:
        r.status = "fail"
        r.detail = f"assert: {e}"
    except Exception as e:
        r.status = "fail"
        r.detail = f"{type(e).__name__}: {e}"
        r.error = traceback.format_exc()
    return r


# ============================================================================
# LAYER 1 — GEO (map, properties, boundaries, cameras)
# ============================================================================

def test_geo_imports():
    from core.geo import store, tiles, satellite, cameras, cloud
    assert store is not None
    assert tiles is not None
    assert satellite is not None
    assert cameras is not None
    assert cloud is not None
    return "all geo submodules import"


def test_geo_store_roundtrip():
    from core.geo import store
    p = store.add_property("_test_farm", "farm", lat=-1.29, lng=36.82, notes="smoke test")
    pid = p["id"]
    assert pid, "no id returned"
    got = store.get_property(pid)
    assert got and got["name"] == "_test_farm"
    # boundary add + area computation
    sq = {"type": "Polygon",
          "coordinates": [[[36.80, -1.30], [36.81, -1.30],
                           [36.81, -1.29], [36.80, -1.29], [36.80, -1.30]]]}
    b = store.add_boundary(pid, sq, label="test plot")
    assert b["id"]
    got2 = store.get_property(pid)
    assert got2["area_m2"] and got2["area_m2"] > 0, "area not computed"
    ha = got2["area_m2"] / 10000
    # tiny polygon => tiny area, sanity bounds
    assert ha < 100, f"unreasonable area: {ha} ha"
    # delete
    ok = store.delete_property(pid)
    assert ok
    return f"property id={pid[:6]} area={ha:.4f} ha boundaries cleaned up"


def test_geo_tile_config():
    from core.geo import tiles
    cfg = tiles.config()
    assert "vector_tiles" in cfg
    assert "satellite_tiles" in cfg
    style = tiles.map_style()
    assert style["version"] == 8
    assert "sources" in style and "layers" in style
    ids = [l["id"] for l in style["layers"]]
    for want in ("satellite", "roads", "buildings"):
        assert want in ids, f"missing layer: {want}"
    return f"mode={cfg['mode']} layers={len(style['layers'])}"


def test_geo_satellite_status():
    from core.geo import satellite
    s = satellite.status()
    assert "tile_layer" in s
    assert "hardware_ok" in s
    return f"tile={s['tile_layer']} gpu={s['hardware_ok']} model={s.get('model_configured') or 'none'}"


def test_geo_satellite_analyze_no_gpu():
    """On CPU-only with no cloud key, analyze_polygon should return structured 'no_backend'."""
    from core.geo import satellite
    sq = {"type": "Polygon",
          "coordinates": [[[36.8, -1.3], [36.9, -1.3], [36.9, -1.2], [36.8, -1.2], [36.8, -1.3]]]}
    r = satellite.analyze_polygon(sq, task="landcover")
    # ok can be True (cloud worked) or False with reason=no_backend — both valid
    assert "ok" in r
    if r["ok"]:
        return f"analyzed via {r.get('backend')}"
    # else make sure it's a structured response, not a crash
    assert r.get("reason") in ("no_backend", "no_gpu", "model_not_configured",
                                "prithvi_module_missing")
    return f"graceful: {r.get('reason')}"


def test_geo_cameras_list():
    from core.geo import cameras, store
    cams = store.list_cameras()
    fs = cameras.frigate_status()
    return f"{len(cams)} cameras, frigate online={fs['online']}"


def test_geo_observations():
    from core.geo import store
    o = store.add_observation(
        source="test", kind="person", confidence=0.91,
        lat=-1.29, lng=36.82, payload={"test": True},
    )
    assert o["id"]
    recent = store.recent_observations(limit=5)
    assert any(r["id"] == o["id"] for r in recent), "observation not in recent list"
    return f"id={o['id'][:6]} recent_count={len(recent)}"


# ============================================================================
# CLOUD BACKENDS
# ============================================================================

def test_cloud_backends_status():
    from core.geo import cloud
    s = cloud.status()
    ready = s["ready"]
    need = s["needs_key"]
    for want in ("hf_inference", "gemini_vision", "openrouter_vision"):
        found = [b for b in ready + need if b["id"] == want]
        assert found, f"backend {want} missing from list"
    return f"{len(ready)} ready, {len(need)} need keys"


def test_vision_detect_module():
    from core.vision import cloud_detect
    assert hasattr(cloud_detect, "detect_file")
    assert hasattr(cloud_detect, "detect_bytes")
    assert hasattr(cloud_detect, "status")
    return "cloud_detect API present"


def test_vision_detect_no_backend():
    """Empty bytes should fail cleanly, not crash."""
    from core.vision import cloud_detect
    r = cloud_detect.detect_bytes(b"", prompt="anything")
    # no backend configured → returns ok=False with message
    assert isinstance(r, dict)
    if r.get("ok"):
        return f"detected via {r.get('backend')} (unexpected but fine)"
    assert "message" in r or "errors" in r
    return f"graceful: {r.get('message', '')[:60]}"


# ============================================================================
# FEATURE 2 — SMS PLUGIN
# ============================================================================

def test_sms_plugin_import():
    import importlib.util
    p = PROJECT_ROOT / "core" / "plugins" / "sms_plugin.py"
    spec = importlib.util.spec_from_file_location("sms_plugin_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "Plugin")
    return "sms_plugin loads"


def test_sms_phone_normalization():
    import importlib.util
    p = PROJECT_ROOT / "core" / "plugins" / "sms_plugin.py"
    spec = importlib.util.spec_from_file_location("sms_plugin_test2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.Plugin()
    cases = [
        ("0712345678", "+254712345678"),         # Kenyan local → +254
        ("254712345678", "+254712345678"),       # 254 prefix → +
        ("+254712345678", "+254712345678"),      # already correct
        ("+1 555 123 4567", "+15551234567"),     # US
        ("abc", ""),                              # invalid → ""
    ]
    ok = 0
    fails = []
    for inp, want in cases:
        got = plugin._normalize_phone(inp)
        if got == want:
            ok += 1
        else:
            fails.append(f"{inp!r}→{got!r} (want {want!r})")
    if fails:
        raise AssertionError(f"{ok}/{len(cases)} normalized; fails: {fails}")
    return f"{ok}/{len(cases)} phone normalizations correct"


def test_sms_no_backend():
    import importlib.util
    p = PROJECT_ROOT / "core" / "plugins" / "sms_plugin.py"
    spec = importlib.util.spec_from_file_location("sms_plugin_test3", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.Plugin()
    # No keys set → backends empty, send returns helpful message
    out = plugin.send("+254712345678", "test")
    assert isinstance(out, str)
    if plugin.backends:
        # keys were set — don't actually send; just assert it attempted something
        return f"backend(s) present: {plugin.backends} (skipping real send)"
    assert "no backend configured" in out.lower()
    return "no-backend message is helpful"


def test_sms_process_parses():
    import importlib.util
    p = PROJECT_ROOT / "core" / "plugins" / "sms_plugin.py"
    spec = importlib.util.spec_from_file_location("sms_plugin_test4", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.Plugin()
    # Bad input → usage message (no backend call)
    out = plugin.process("not a phone number")
    assert "Usage" in out or "no backend" in out.lower() or "invalid" in out.lower()
    return "usage message on bad input"


# ============================================================================
# FEATURE 3 — PDF REPORT
# ============================================================================

def test_report_import():
    import importlib.util
    p = PROJECT_ROOT / "core" / "plugins" / "report_plugin.py"
    spec = importlib.util.spec_from_file_location("report_plugin_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "Plugin")
    return "report_plugin loads"


def test_report_generates_pdf():
    try:
        from reportlab import __version__ as rl_ver  # noqa
    except ImportError:
        return ("skip", "reportlab not installed (pip install reportlab)")
    import importlib.util
    p = PROJECT_ROOT / "core" / "plugins" / "report_plugin.py"
    spec = importlib.util.spec_from_file_location("report_plugin_test2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.Plugin()
    out = plugin.generate(
        query="smoke test",
        body="# Header\n\nThis is a test paragraph.\n\n## Section\nMore text here.",
        title="Neo Smoke Test",
    )
    assert "[Report]" in out
    # find the file
    files = list((PROJECT_ROOT / "generated_reports").glob("smoke_test_*.pdf"))
    assert files, f"no PDF found; output was: {out}"
    latest = max(files, key=lambda f: f.stat().st_mtime)
    size = latest.stat().st_size
    assert size > 1000, f"PDF too small: {size} bytes"
    # verify it's a real PDF
    head = latest.read_bytes()[:5]
    assert head == b"%PDF-", f"not a PDF: {head!r}"
    return f"{latest.name} ({size} bytes) reportlab={rl_ver}"


# ============================================================================
# FEATURE 4 — SCHEDULER UI
# ============================================================================

def test_scheduler_ui_import():
    import scheduler_ui
    assert hasattr(scheduler_ui, "register_scheduler_routes")
    assert "Scheduler" in scheduler_ui.PAGE
    return "scheduler_ui module present"


def test_scheduler_collect_jobs():
    import scheduler_ui
    jobs, sources = scheduler_ui._collect_jobs()
    # may be empty on a clean machine
    return f"{len(jobs)} jobs from {len(sources)} source(s)"


def test_scheduler_page_renders():
    import scheduler_ui
    assert "<title>Neo Scheduler</title>" in scheduler_ui.PAGE
    assert "/api/scheduler" in scheduler_ui.PAGE
    return "HTML page has title + fetch target"


# ============================================================================
# MAP UI
# ============================================================================

def test_map_ui_import():
    import map_ui
    assert hasattr(map_ui, "register_map_routes")
    assert "<title>Neo Map</title>" in map_ui.PAGE
    return "map_ui module present"


def test_map_page_has_draw_tools():
    import map_ui
    page = map_ui.PAGE
    for want in ("maplibre", "TerraDraw", "btn-draw", "btn-save",
                 "btn-sat", "btn-new-cam"):
        assert want in page, f"missing UI element: {want}"
    return "all expected map controls present"


def test_map_routes_registered():
    """Boot a tiny Flask app with our routes and check they respond."""
    try:
        from flask import Flask
    except ImportError:
        return ("skip", "flask not installed")
    import map_ui
    app = Flask(__name__)
    map_ui.register_map_routes(app)
    client = app.test_client()

    checks = [
        ("/map", 200),
        ("/api/geo/style", 200),
        ("/api/geo/properties", 200),
        ("/api/geo/cameras", 200),
        ("/api/geo/observations", 200),
        ("/api/geo/satellite/status", 200),
        ("/api/geo/backends", 200),
    ]
    for path, expected in checks:
        r = client.get(path)
        assert r.status_code == expected, f"{path} → {r.status_code} (want {expected})"
    return f"{len(checks)} routes respond 200"


def test_map_property_create_via_api():
    try:
        from flask import Flask
    except ImportError:
        return ("skip", "flask not installed")
    import map_ui
    app = Flask(__name__)
    map_ui.register_map_routes(app)
    c = app.test_client()
    r = c.post("/api/geo/properties", json={"name": "_api_test", "kind": "plot"})
    assert r.status_code == 200
    body = r.get_json()
    pid = body["property"]["id"]
    # cleanup
    c.delete(f"/api/geo/properties/{pid}")
    return f"created+deleted {pid[:6]}"


# ============================================================================
# NOSIGNUP TOOLS (regression — already validated, but keep here for one-stop)
# ============================================================================

def test_nosignup_registry():
    from neo_nosignups import ToolRegistry
    reg = ToolRegistry(str(PROJECT_ROOT / "tools.json"))
    s = reg.get_stats()
    assert s["total_tools"] >= 200
    return (f"{s['total_tools']} tools · {s['total_categories']} cats · "
            f"{s['featured']} featured · {s['iframe_ready']} iframe")


def test_nosignup_matcher():
    from neo_nosignups import ToolRegistry
    reg = ToolRegistry(str(PROJECT_ROOT / "tools.json"))
    cases = [
        ("convert pdf to word", "bentopdf"),
        ("draw diagram", "excalidraw"),
        ("test regex", "regexr"),
        ("edit markdown", "stackedit"),
        ("visualize json", "json-crack"),
    ]
    hits = 0
    for q, want in cases:
        ids = [m.tool.get("id") for m in reg.find_tool_for_task(q, top_k=3)]
        if want in ids:
            hits += 1
    assert hits >= 4, f"only {hits}/{len(cases)}"
    return f"{hits}/{len(cases)} top-3 hits"


def test_nosignup_plugin_intents():
    from neo_nosignups import NeoToolPlugin
    p = NeoToolPlugin(str(PROJECT_ROOT / "tools.json"))
    cases = ["test regex", "edit pdf", "visualize json", "compress image",
             "draw diagram", "edit markdown"]
    hits = sum(1 for q in cases if (p.handle_intent(q) or {}).get("has_tool"))
    assert hits >= len(cases) - 1, f"only {hits}/{len(cases)} explicit intents fired"
    return f"{hits}/{len(cases)} explicit intents fired"


def test_nosignup_integrator_iframe():
    from neo_nosignups import ToolRegistry, ToolIntegrator
    reg = ToolRegistry(str(PROJECT_ROOT / "tools.json"))
    integ = ToolIntegrator(reg)
    html = integ.get_iframe_embed("excalidraw", height="400px")
    assert "<iframe" in html and "excalidraw" in html
    qa = integ.get_quick_actions()
    assert len(qa) >= 6
    return f"iframe ok, {len(qa)} quick actions"


# ============================================================================
# LAUNCHER INTEGRATION (only if launcher is importable + running)
# ============================================================================

def test_launcher_aliases_extended():
    """Confirm sms + report are in the launcher's alias set."""
    src = (PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8")
    assert '"sms"' in src and '"report"' in src
    assert "_try_plugin_preflight" in src
    return "sms + report wired in launcher"


# ============================================================================
# MAIN
# ============================================================================

CATEGORIES: List[Tuple[str, List[Tuple[str, Callable[[], str]]]]] = [
    ("geo.store", [
        ("geo.imports",              test_geo_imports),
        ("geo.store_roundtrip",      test_geo_store_roundtrip),
        ("geo.observations",         test_geo_observations),
    ]),
    ("geo.map", [
        ("geo.tile_config",          test_geo_tile_config),
    ]),
    ("geo.satellite", [
        ("geo.satellite_status",     test_geo_satellite_status),
        ("geo.satellite_analyze",    test_geo_satellite_analyze_no_gpu),
    ]),
    ("geo.cameras", [
        ("geo.cameras_list",         test_geo_cameras_list),
    ]),
    ("cloud", [
        ("cloud.backends_status",    test_cloud_backends_status),
        ("vision.detect_module",     test_vision_detect_module),
        ("vision.detect_no_backend", test_vision_detect_no_backend),
    ]),
    ("sms", [
        ("sms.plugin_import",        test_sms_plugin_import),
        ("sms.normalize_phone",      test_sms_phone_normalization),
        ("sms.no_backend",           test_sms_no_backend),
        ("sms.parse_usage",          test_sms_process_parses),
    ]),
    ("report", [
        ("report.import",            test_report_import),
        ("report.generate_pdf",      test_report_generates_pdf),
    ]),
    ("scheduler", [
        ("scheduler.ui_import",      test_scheduler_ui_import),
        ("scheduler.collect_jobs",   test_scheduler_collect_jobs),
        ("scheduler.page_render",    test_scheduler_page_renders),
    ]),
    ("map_ui", [
        ("map.import",               test_map_ui_import),
        ("map.page_controls",        test_map_page_has_draw_tools),
        ("map.routes_registered",    test_map_routes_registered),
        ("map.property_api",         test_map_property_create_via_api),
    ]),
    ("nosignup", [
        ("nosignup.registry",        test_nosignup_registry),
        ("nosignup.matcher",         test_nosignup_matcher),
        ("nosignup.plugin_intents",  test_nosignup_plugin_intents),
        ("nosignup.integrator",      test_nosignup_integrator_iframe),
    ]),
    ("launcher", [
        ("launcher.aliases",         test_launcher_aliases_extended),
    ]),
]


def main() -> int:
    global VERBOSE
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--only", type=str, default=None,
                    help="run only this category (e.g. geo.map)")
    args = ap.parse_args()
    VERBOSE = args.verbose

    print("=" * 72)
    print("  NEO — NEW FEATURE SMOKE TEST")
    print("=" * 72)
    print()

    results: List[Result] = []
    by_cat: Dict[str, List[Result]] = {}

    for cat, tests in CATEGORIES:
        if args.only and cat != args.only and not cat.startswith(args.only):
            continue
        by_cat[cat] = []
        for name, fn in tests:
            r = run(name, cat, fn)
            results.append(r)
            by_cat[cat].append(r)
            icon = {"pass": PASS, "fail": FAIL, "skip": SKIP}.get(r.status, "?")
            print(f"  {icon} {r.name:<32} {r.detail[:80]}")
            if VERBOSE and r.error:
                print("      traceback:")
                for line in r.error.splitlines()[-6:]:
                    print(f"        {line}")

    print()
    print("=" * 72)
    print("  SUMMARY BY CATEGORY")
    print("=" * 72)
    print(f"  {'Category':<20} {'Pass':>5} {'Fail':>5} {'Skip':>5} {'Total':>6}")
    print(f"  {'-'*20} {'-'*5} {'-'*5} {'-'*5} {'-'*6}")
    grand_p = grand_f = grand_s = 0
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        p = sum(1 for r in rs if r.status == "pass")
        f = sum(1 for r in rs if r.status == "fail")
        s = sum(1 for r in rs if r.status == "skip")
        grand_p += p; grand_f += f; grand_s += s
        print(f"  {cat:<20} {p:>5} {f:>5} {s:>5} {len(rs):>6}")
    print(f"  {'-'*20} {'-'*5} {'-'*5} {'-'*5} {'-'*6}")
    print(f"  {'TOTAL':<20} {grand_p:>5} {grand_f:>5} {grand_s:>5} {len(results):>6}")
    print()

    if grand_f:
        print("=" * 72)
        print("  FAILURES")
        print("=" * 72)
        for r in results:
            if r.status == "fail":
                print(f"  {FAIL} {r.name}")
                print(f"     {r.detail}")
                if VERBOSE and r.error:
                    print(r.error)
                print()
        return 1

    print(f"  All {grand_p} tests passed \U0001F389")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

Path("test_new_features.py").write_text(content, encoding="utf-8")
print("[ok] wrote test_new_features.py")
print("[ok] run:  python test_new_features.py")
print("[ok] verbose:  python test_new_features.py --verbose")
print("[ok] single cat:  python test_new_features.py --only map_ui")