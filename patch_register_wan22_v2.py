#!/usr/bin/env python3
"""patch_register_wan22_v2.py -- register WAN 2.2 adapter + provider entry.
YAML manipulation via load/dump (comments already stripped by earlier trim).
"""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml missing"); sys.exit(1)

# ---------- 1. Registry ----------
reg_path = ROOT / "core" / "video_adapter_registry.py"
if not reg_path.exists():
    print(f"ERROR: {reg_path} not found"); sys.exit(1)

reg = reg_path.read_text(encoding="utf-8")
if "tier0_wan22" in reg:
    print("  registry: already has tier0_wan22 -- skip")
else:
    anchor = '"tier0_whisk":'
    if anchor not in reg:
        print(f"ERROR: registry anchor '{anchor}' not found")
        print("Registry content (first 30 lines):")
        for i, line in enumerate(reg.splitlines()[:30], 1):
            print(f"  {i:2d}: {line}")
        sys.exit(1)
    # find the line containing the whisk entry and add wan22 after it
    lines = reg.splitlines()
    out = []
    for line in lines:
        out.append(line)
        if anchor in line:
            out.append('    "tier0_wan22":      ("core.video_adapters.tier0_gradio",     "Wan22Adapter"),')
    new_reg = chr(10).join(out) + chr(10)
    try:
        ast.parse(new_reg)
    except SyntaxError as e:
        print(f"ERROR: registry patch would break syntax: {e}"); sys.exit(1)
    if DRY_RUN:
        print(f"  registry: DRY-RUN would add tier0_wan22")
    else:
        bak = reg_path.with_suffix(".py.bak")
        bak.write_bytes(reg_path.read_bytes())
        reg_path.write_text(new_reg, encoding="utf-8")
        print(f"  registry: OK (backup: {bak.name})")

# ---------- 2. YAML via load/dump ----------
yaml_path = ROOT / "config" / "video_providers.yaml"
if not yaml_path.exists():
    print(f"ERROR: {yaml_path} not found"); sys.exit(1)

data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
if not isinstance(data, dict) or "providers" not in data:
    print("ERROR: unexpected YAML structure"); sys.exit(1)

names = [p.get("name") for p in data["providers"]]
if "wan22-hf" in names:
    print("  yaml: already has wan22-hf -- skip")
else:
    wan_entry = {
        "name": "wan22-hf",
        "tier": 0,
        "endpoint": "https://zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space",
        "auth": "none",
        "adapter": "tier0_wan22",
        "models": ["wan-2.2-fp8"],
        "daily_quota": None,
        "per_user_daily_cap": 5,
        "reliability": 0.65,
        "enabled_flag": "TIER0_ENABLED",
    }
    # insert before the first tier-1 provider so Tier 0 stays grouped
    insert_at = len(data["providers"])
    for i, p in enumerate(data["providers"]):
        if p.get("tier", 0) >= 1:
            insert_at = i
            break
    data["providers"].insert(insert_at, wan_entry)

    new_yaml = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    # validate round-trip
    check = yaml.safe_load(new_yaml)
    check_names = [p["name"] for p in check["providers"]]
    assert "wan22-hf" in check_names, "wan22-hf missing after round-trip"
    print(f"  yaml: patch validates ({len(check_names)} providers, wan22 at index {insert_at})")

    if DRY_RUN:
        print(f"  yaml: DRY-RUN would update {yaml_path}")
    else:
        bak = yaml_path.with_suffix(".yaml.bak")
        bak.write_bytes(yaml_path.read_bytes())
        yaml_path.write_text(new_yaml, encoding="utf-8")
        print(f"  yaml: OK (backup: {bak.name})")

print()
if DRY_RUN:
    print("DRY-RUN complete. If output above looks correct, run without --dry-run.")
else:
    print("Verify: python -c \"from core.video_router import VideoRouter; r=VideoRouter.from_config('config/video_providers.yaml'); print(len(r.providers), 'providers;', sorted(r.adapters))\"")