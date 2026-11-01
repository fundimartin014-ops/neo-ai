#!/usr/bin/env python3
"""fix_wan22_duration.py -- clamp duration to 3.5 (Space default, proven safe)."""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv

target = ROOT / "core" / "video_adapters" / "tier0_gradio.py"
if not target.exists():
    print(f"ERROR: {target} not found"); sys.exit(1)

content = target.read_text(encoding="utf-8")
old = "duration = min(max(float(req.duration or 3.5), 1.0), 4.0)"
new = "duration = min(max(float(req.duration or 3.5), 1.0), 3.5)"
if new in content:
    print("  already clamped to 3.5 -- skip"); sys.exit(0)
if old not in content:
    print(f"ERROR: could not find clamp line")
    for i, line in enumerate(content.splitlines(), 1):
        if "duration" in line and "min(max" in line:
            print(f"  line {i}: {line}")
    sys.exit(1)

new_content = content.replace(old, new, 1)
try:
    ast.parse(new_content)
    print("  patched code parses OK")
except SyntaxError as e:
    print(f"ERROR: patch would break: {e}"); sys.exit(1)

if DRY_RUN:
    print(f"DRY-RUN: would clamp to 3.5 in {target.name}"); sys.exit(0)

bak = target.with_suffix(".py.bak3")
bak.write_bytes(target.read_bytes())
print(f"  backup: {bak.name}")
target.write_text(new_content, encoding="utf-8")
print(f"  OK: {target}")