#!/usr/bin/env python3
"""fix_wan22_import.py -- Add missing 'from urllib.parse import quote' to adapter."""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv

target = ROOT / "core/video_adapters/tier0_gradio.py"
if not target.exists():
    print(f"ERROR: {target} not found")
    sys.exit(1)

content = target.read_text(encoding="utf-8")

if "from urllib.parse import quote" in content:
    print("  already fixed -- import present")
    sys.exit(0)

# Insert after the existing 'from pathlib import Path' line
marker = "from pathlib import Path"
if marker not in content:
    print(f"ERROR: could not find '{marker}' to anchor the insertion")
    sys.exit(1)

new_content = content.replace(
    marker,
    marker + chr(10) + "from urllib.parse import quote",
    1,
)

try:
    ast.parse(new_content)
    print("  patched code parses OK")
except SyntaxError as e:
    print(f"ERROR: patch would break syntax: {e}"); sys.exit(1)

if DRY_RUN:
    print(f"DRY-RUN: would insert import into {target}")
    sys.exit(0)

bak = target.with_suffix(".py.bak2")
bak.write_bytes(target.read_bytes())
print(f"  backup: {bak.name}")

try:
    target.write_text(new_content, encoding="utf-8")
    print(f"  OK: {target}")
except Exception as e:
    target.write_bytes(bak.read_bytes())
    print(f"  ROLLBACK: {e}"); sys.exit(1)

print()
print("Verifying import is present:")
for i, line in enumerate(new_content.splitlines()[:15], 1):
    if "urllib" in line or "pathlib" in line:
        print(f"  line {i}: {line}")