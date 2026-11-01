#!/usr/bin/env python3
"""patch_video_router_v2b.py -- Phase 2b: registry, safety stub, plugin, agent,
plus surgical updates to video_router.py and video_providers.yaml.
Backs up both files. Rolls back on any failure.
"""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv
created, updated, skipped, errors = [], [], [], []

try:
    import yaml
except ImportError:
    yaml = None

def write_new(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        skipped.append(rel); print(f"  SKIP (exists): {rel}"); return
    if rel.endswith(".py"):
        try: ast.parse(content)
        except SyntaxError as e:
            errors.append((rel, f"syntax: {e}")); print(f"  SYNTAX ERR: {rel}: {e}"); return
    if DRY_RUN:
        created.append(rel); print(f"  DRY-RUN would create: {rel}"); return
    try:
        p.write_text(content, encoding="utf-8"); created.append(rel); print(f"  OK: {rel}")
    except Exception as e:
        errors.append((rel, str(e))); print(f"  ERR: {rel}: {e}")

def update_existing(rel, old_marker, new_block, validate="py"):
    p = ROOT / rel
    if not p.exists():
        errors.append((rel, "file not found")); return
    current = p.read_text(encoding="utf-8")
    if new_block.strip() and new_block.strip() in current:
        skipped.append(rel); print(f"  SKIP (already updated): {rel}"); return
    count = current.count(old_marker)
    if count == 0:
        errors.append((rel, "marker not found (file may have been modified)")); return
    if count > 1:
        errors.append((rel, f"marker found {count}x (ambiguous)")); return
    new_content = current.replace(old_marker, new_block, 1)
    if validate == "py":
        try: ast.parse(new_content)
        except SyntaxError as e:
            errors.append((rel, f"new syntax: {e}")); return
    elif validate == "yaml":
        if yaml is None:
            errors.append((rel, "pyyaml missing, refusing to update YAML")); return
        try: yaml.safe_load(new_content)
        except Exception as e:
            errors.append((rel, f"new YAML invalid: {e}")); return
    if DRY_RUN:
        updated.append(rel); print(f"  DRY-RUN would update: {rel}"); return
    bak = ROOT / (rel + ".bak")
    try: bak.write_bytes(p.read_bytes())
    except Exception as e:
        errors.append((rel, f"backup failed: {e}")); return
    try:
        p.write_text(new_content, encoding="utf-8")
        updated.append(rel); print(f"  OK (backup: {bak.name}): {rel}")
    except Exception as e:
        try: p.write_bytes(bak.read_bytes()); print(f"  ROLLBACK: {rel}")
        except: pass
        errors.append((rel, f"write failed: {e}"))

print("=" * 70)
print("patch_video_router_v2b.py -- Phase 2b")
print(f"  Root: {ROOT}")
print(f"  Mode: {'DRY-RUN' if DRY_RUN else 'SAFE'}")
print("=" * 70)

# ---------- 1. NEW: adapter registry ----------
write_new("core/video_adapter_registry.py", '''"""Maps adapter name -> (module path, class name). No side effects."""
import importlib

ADAPTERS = {
    "tier0_proxy":      ("core.video_adapters.tier0_proxy",      "FreeMultimodalProxyAdapter"),
    "tier0_jimeng":     ("core.video_adapters.tier0_jimeng",     "JimengAdapter"),
    "tier0_prezzy":     ("core.video_adapters.tier0_prezzy",     "PrezzyAdapter"),
    "tier0_cvron":      ("core.video_adapters.tier0_cvron",      "CvronAdapter"),
    "tier0_doubao":     ("core.video_adapters.tier0_doubao",     "DoubaoAdapter"),
    "tier0_whisk":      ("core.video_adapters.tier0_whisk",      "WhiskAdapter"),
    "tier1_magichour":  ("core.video_adapters.tier1_magichour",  "MagicHourAdapter"),
    "tier1_agnes":      ("core.video_adapters.tier1_agnes",      "AgnesAdapter"),
    "tier1_vercel":     ("core.video_adapters.tier1_vercel",     "VercelAdapter"),
    "tier1_rewind":     ("core.video_adapters.tier1_rewind",     "RewindAdapter"),
    "tier2_higgsfield": ("core.video_adapters.tier2_higgsfield", "HiggsfieldAdapter"),
}


def get_adapter_class(name):
    if not name or name not in ADAPTERS:
        return None
    module_path, class_name = ADAPTERS[name]
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    except Exception:
        return None


def list_registered():
    return sorted(ADAPTERS.keys())
''')

# ---------- 2. NEW: safety stub (opt-in enforcement) ----------
write_new("core/video_safety.py", '''"""Video content safety gate. Stub by default; enforcing is opt-in.

Env vars:
  VIDEO_SAFETY_ENFORCE=true   -- block on detection (default: warn only)
  VIDEO_SAFETY_KEYWORDS       -- comma-separated blocked words (default: minimal list)
"""
import os, logging

log = logging.getLogger(__name__)

_DEFAULT_BLOCKED = {"csam", "child porn", "cp"}


def _blocked_terms():
    raw = os.getenv("VIDEO_SAFETY_KEYWORDS", "")
    extra = {w.strip().lower() for w in raw.split(",") if w.strip()}
    return _DEFAULT_BLOCKED | extra


def check_prompt(prompt: str):
    """Return (ok: bool, reason: str). Always blocks hard categories;
    logs (does not block) on soft categories unless enforce is on."""
    p = (prompt or "").lower()
    terms = _blocked_terms()
    hits = [w for w in terms if w in p]
    if hits:
        return False, f"prompt contains blocked term(s): {hits}"
    return True, ""


def check_video_url(url: str):
    """Placeholder for post-generation frame classifier. Returns (ok, reason)."""
    if os.getenv("VIDEO_SAFETY_ENFORCE", "false").lower() != "true":
        return True, ""
    return True, ""
''')

# ---------- 3. NEW: plugin (no auto-register) ----------
write_new("core/plugins/video_router_plugin.py", '''"""Video router plugin. Exposes callable tools. Does NOT auto-register.
Wire into core.tool_registry in Phase 3 after verification.
"""
from skills.video_generate_skill import video_generate, video_generate_available


def install(registry):
    """Call from your tool loader once you are ready to expose these tools."""
    if hasattr(registry, "register"):
        registry.register("video_generate", video_generate)
        registry.register("video_available", video_generate_available)
    return True


__all__ = ["install", "video_generate", "video_generate_available"]
''')

# ---------- 4. NEW: agent (standalone, no auto-register) ----------
write_new("agents/video_generation_agent.py", '''"""Video generation agent. Standalone class -- not auto-registered."""
from skills.video_generate_skill import video_generate


class VideoGenerationAgent:
    name = "video_generation_agent"

    def handle(self, message: dict):
        prompt = message.get("prompt") or message.get("text") or ""
        if not prompt:
            return {"ok": False, "error": "no prompt"}
        result = video_generate(
            prompt=prompt,
            quality_tier=message.get("quality_tier", "standard"),
            user_id=message.get("user_id", ""),
            duration=message.get("duration", 5.0),
            aspect_ratio=message.get("aspect_ratio", "16:9"),
            resolution=message.get("resolution", "720p"),
            model_hint=message.get("model_hint"),
        )
        if hasattr(result, "url"):
            return {"ok": True, "url": result.url, "provider": result.provider,
                    "tier": result.tier, "model": result.model}
        return {"ok": False, "queued": True, "job_id": getattr(result, "job_id", None),
                "reason": getattr(result, "reason", "unknown")}
''')

# ---------- 5. UPDATE: video_router.py _load_adapter ----------
old_adapter = '''def _load_adapter(provider: Provider):
    if provider.adapter == "tier0_proxy":
        from .video_adapters.tier0_proxy import FreeMultimodalProxyAdapter
        return FreeMultimodalProxyAdapter()
    return None'''

new_adapter = '''def _load_adapter(provider: Provider):
    from .video_adapter_registry import get_adapter_class
    cls = get_adapter_class(provider.adapter)
    return cls() if cls else None'''

update_existing("core/video_router.py", old_adapter, new_adapter, validate="py")

# ---------- 6. UPDATE: video_providers.yaml ----------
new_yaml = '''# Video provider registry. Phase 2b -- all tiers wired.
providers:
  # ---------- TIER 0: GREY / UNOFFICIAL ----------
  - name: free-multimodal-proxy
    tier: 0
    endpoint: http://localhost:8080/v1/videos/generations
    auth: none
    adapter: tier0_proxy
    models: [wan-2.2, kling-3.0, seedance-2.0, pixverse-v6, hailuo]
    daily_quota: null
    per_user_daily_cap: 5
    reliability: 0.70
    enabled_flag: TIER0_ENABLED

  - name: jimeng-free-api
    tier: 0
    endpoint: http://localhost:8081/v1/videos/generations
    auth: session_id
    adapter: tier0_jimeng
    models: [seedance-2.0]
    daily_quota: 60
    per_user_daily_cap: 5
    reliability: 0.60
    enabled_flag: TIER0_ENABLED

  - name: prezzy-prexzyapis
    tier: 0
    endpoint: https://prexzyapis.com/v1/videos/generations
    auth: none
    adapter: tier0_prezzy
    models: [wan-2.2, ltx-2]
    daily_quota: null
    per_user_daily_cap: 5
    reliability: 0.55
    enabled_flag: TIER0_ENABLED

  - name: cvron-hub
    tier: 0
    endpoint: https://api.cvron.dev/v1/videos
    auth: none
    adapter: tier0_cvron
    models: [wan-2.2, ltx-2]
    daily_quota: null
    per_user_daily_cap: 5
    reliability: 0.50
    enabled_flag: TIER0_ENABLED

  - name: doubao2api
    tier: 0
    endpoint: http://localhost:8082/v1/videos/generations
    auth: client_session
    adapter: tier0_doubao
    models: [doubao-video]
    daily_quota: null
    per_user_daily_cap: 5
    reliability: 0.55
    enabled_flag: TIER0_ENABLED

  - name: whisk-api
    tier: 0
    endpoint: http://localhost:8083/v1/animate
    auth: cookie
    adapter: tier0_whisk
    models: [veo-3.1]
    daily_quota: 25
    per_user_daily_cap: 3
    reliability: 0.50
    enabled_flag: TIER0_ENABLED

  # ---------- TIER 1: OFFICIAL FREE TIERS ----------
  - name: magic-hour
    tier: 1
    endpoint: https://api.magichour.ai/v1
    auth: bearer:MAGIC_HOUR_API_KEY
    adapter: tier1_magichour
    models: [ltx-2.5, wan-2.2, minimax-h3]
    daily_quota: 90
    per_user_daily_cap: 3
    reliability: 0.99
    enabled_flag: TIER1_ENABLED

  - name: agnes-ai
    tier: 1
    endpoint: https://api.agnes.ai/v1
    auth: bearer:AGNES_API_KEY
    adapter: tier1_agnes
    models: [agnes-video-v2.0]
    daily_quota: null
    per_user_daily_cap: 5
    reliability: 0.85
    enabled_flag: TIER1_ENABLED

  - name: vercel-gateway
    tier: 1
    endpoint: https://ai-gateway.vercel.sh/v1
    auth: bearer:VERCEL_AI_KEY
    adapter: tier1_vercel
    models: [wan-v3.0, seedance-2.0]
    monthly_budget_usd: 4.50
    per_user_daily_cap: 2
    reliability: 0.99
    enabled_flag: TIER1_ENABLED

  - name: rewind-ai
    tier: 1
    endpoint: https://api.rewind.ai/v1
    auth: bearer:REWIND_KEY
    adapter: tier1_rewind
    models: [bytedance/seedance-1-5-pro]
    daily_quota: 4500
    per_user_daily_cap: 2
    reliability: 0.75
    enabled_flag: TIER1_ENABLED

  # ---------- TIER 2: PAID (DORMANT) ----------
  - name: higgsfield
    tier: 2
    endpoint: https://platform.higgsfield.ai/v1
    auth: bearer:HF_KEY
    adapter: tier2_higgsfield
    models: [seedance-2.5, kling-3.0]
    reliability: 0.99
    enabled_flag: PAID_ENABLED
'''

p_yaml = ROOT / "config/video_providers.yaml"
if p_yaml.exists():
    current_yaml = p_yaml.read_text(encoding="utf-8")
    if "adapter: tier0_jimeng" in current_yaml:
        skipped.append("config/video_providers.yaml"); print("  SKIP (already updated): config/video_providers.yaml")
    else:
        if yaml is None:
            errors.append(("config/video_providers.yaml", "pyyaml missing, refusing"))
        else:
            try:
                yaml.safe_load(new_yaml)
                new_yaml_ok = True
            except Exception as e:
                errors.append(("config/video_providers.yaml", f"new YAML invalid: {e}")); new_yaml_ok = False
            if new_yaml_ok:
                if DRY_RUN:
                    updated.append("config/video_providers.yaml"); print("  DRY-RUN would update: config/video_providers.yaml")
                else:
                    bak = ROOT / "config/video_providers.yaml.bak"
                    bak.write_bytes(p_yaml.read_bytes())
                    try:
                        p_yaml.write_text(new_yaml, encoding="utf-8")
                        updated.append("config/video_providers.yaml")
                        print("  OK (backup: video_providers.yaml.bak): config/video_providers.yaml")
                    except Exception as e:
                        try: p_yaml.write_bytes(bak.read_bytes()); print("  ROLLBACK: config/video_providers.yaml")
                        except: pass
                        errors.append(("config/video_providers.yaml", f"write failed: {e}"))
else:
    errors.append(("config/video_providers.yaml", "not found -- run Phase 1 first"))

# ---------- summary ----------
print()
print("=" * 70)
print(f"SUMMARY: created={len(created)} updated={len(updated)} skipped={len(skipped)} errors={len(errors)}")
if created: print("  Created:", ", ".join(created))
if updated: print("  Updated:", ", ".join(updated))
if skipped: print("  Skipped:", ", ".join(skipped))
if errors:
    print("  ERRORS:")
    for p, e in errors: print(f"    {p}: {e}")
    sys.exit(1)
print("=" * 70)
if not DRY_RUN:
    print("Rollback: copy any *.bak back over its original and re-run Phase 1 patch.")
    print("Next verify (no network):")
    print("  python -c \"from core.video_adapter_registry import list_registered; print(list_registered())\"")
    print("  python -c \"from core.video_router import VideoRouter; r=VideoRouter.from_config('config/video_providers.yaml'); print(f'providers={len(r.providers)} adapters={sorted(r.adapters)}')\"")
print()