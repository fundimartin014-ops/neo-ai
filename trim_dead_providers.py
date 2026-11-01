#!/usr/bin/env python3
"""trim_dead_providers.py -- Remove DNS-dead providers from YAML. Safe."""
from pathlib import Path
import sys
try:
    import yaml
except ImportError:
    print("ERROR: pyyaml missing"); sys.exit(1)

p = Path(__file__).parent / "config" / "video_providers.yaml"
if not p.exists():
    print(f"ERROR: {p} not found"); sys.exit(1)

data = yaml.safe_load(p.read_text(encoding="utf-8"))
DEAD = {"cvron-hub", "agnes-ai"}
before = [x["name"] for x in data["providers"]]
data["providers"] = [x for x in data["providers"] if x["name"] not in DEAD]
after = [x["name"] for x in data["providers"]]
removed = [n for n in before if n not in after]

if not removed:
    print("No dead providers present -- already trimmed.")
    sys.exit(0)

bak = p.with_suffix(".yaml.bak")
bak.write_bytes(p.read_bytes())
p.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False), encoding="utf-8")
print(f"  backup: {bak.name}")
print(f"  removed: {removed}")
print(f"  remaining: {len(after)} providers")