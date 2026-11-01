#!/usr/bin/env python3
"""patch_register_wan22.py -- Add WAN 2.2 to adapter registry and provider YAML."""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml missing"); sys.exit(1)

errors = []

# ---------- 1. Update adapter registry ----------
reg_path = ROOT / "core" / "video_adapter_registry.py"
if not reg_path.exists():
    print(f"ERROR: {reg_path} not found"); sys.exit(1)

reg = reg_path.read_text(encoding="utf-8")
if "tier0_wan22" in reg:
    print("  registry: already updated")
else:
    anchor = '    "tier0_whisk":      ("core.video_adapters.tier0_whisk",      "WhiskAdapter"),'
    if anchor not in reg:
        print(f"ERROR: registry anchor not found"); sys.exit(1)
    addition = anchor + chr(10) + '    "tier0_wan22":      ("core.video_adapters.tier0_gradio",     "Wan22Adapter"),'
    new_reg = reg.replace(anchor, addition, 1)
    try:
        ast.parse(new_reg)
        print("  registry: patch parses OK")
    except SyntaxError as e:
        print(f"ERROR: registry patch would break: {e}"); sys.exit(1)
    if not DRY_RUN:
        bak = reg_path.with_suffix(".py.bak")
        bak.write_bytes(reg_path.read_bytes())
        reg_path.write_text(new_reg, encoding="utf-8")
        print(f"  registry: OK (backup: {bak.name})")
    else:
        print(f"DRY-RUN: would update {reg_path}")

# ---------- 2. Update YAML ----------
yaml_path = ROOT / "config" / "video_providers.yaml"
if not yaml_path.exists():
    print(f"ERROR: {yaml_path} not found"); sys.exit(1)

ycontent = yaml_path.read_text(encoding="utf-8")
if "wan22-hf" in ycontent:
    print("  yaml: already has wan22-hf")
else:
    marker = "  # ---------- TIER 1: OFFICIAL FREE TIERS ----------"
    if marker not in ycontent:
        print(f"ERROR: yaml marker not found"); sys.exit(1)
    entry = """  - name: wan22-hf
    tier: 0
    endpoint: https://zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space
    auth: none
    adapter: tier0_wan22
    models: [wan-2.2-fp8]
    daily_quota: null
    per_user_daily_cap: 5
    reliability: 0.65
    enabled_flag: TIER0_ENABLED

"""
    new_ycontent = ycontent.replace(marker, entry + marker, 1)
    try:
        data = yaml.safe_load(new_ycontent)
        names = [p["name"] for p in data["providers"]]
        assert "wan22-hf" in names, "wan22-hf not in providers after parse"
        print(f"  yaml: patch parses OK ({len(names)} providers)")
    except Exception as e:
        print(f"ERROR: yaml patch would break: {e}"); sys.exit(1)
    if not DRY_RUN:
        bak = yaml_path.with_suffix(".yaml.bak")
        bak.write_bytes(yaml_path.read_bytes())
        yaml_path.write_text(new_ycontent, encoding="utf-8")
        print(f"  yaml: OK (backup: {bak.name})")
    else:
        print(f"DRY-RUN: would update {yaml_path}")

print()
print("Rollback: copy *.py.bak / *.yaml.bak back over the originals.")