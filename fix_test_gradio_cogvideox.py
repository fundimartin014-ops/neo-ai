#!/usr/bin/env python3
"""fix_test_gradio_cogvideox.py -- writes test file only. Safe."""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv

TEST = """#!/usr/bin/env python3
# Isolated test for CogVideoX HF Space. Uses zero API credits.
import sys, os

print("=" * 60)
print("CogVideoX HF Space test -- free, no credits used")
print("=" * 60)
print("Space: zai-org/CogVideoX-2B-Space")
print("Expected time: 30s - 5min (ZeroGPU queue)")
print()

from core.video_request import VideoRequest
from core.video_adapters.tier0_gradio import CogVideoXAdapter

req = VideoRequest(
    prompt="a cat running in slow motion, cinematic lighting",
    duration=5.0,
    user_id="gradio-test",
)

print(f"  Prompt: {req.prompt}")
print("  Calling Space... (do not close this window)")
print()

try:
    result = CogVideoXAdapter().generate(req)
    print()
    print("=== SUCCESS ===")
    print(f"  Provider: {result.provider}")
    print(f"  Model:    {result.model}")
    print(f"  Latency:  {result.latency_ms} ms")
    print(f"  File:     {result.url}")
    if os.path.exists(result.url):
        size = os.path.getsize(result.url)
        print(f"  Size:     {size:,} bytes")
except Exception as e:
    print()
    print("=== FAILED ===")
    print(f"  {type(e).__name__}: {e}")
    sys.exit(2)
"""

try:
    ast.parse(TEST)
    print("  generated test code parses OK")
except SyntaxError as e:
    print(f"ERROR: syntax in generated test: {e}")
    sys.exit(1)

target = ROOT / "test_gradio_cogvideox.py"
if DRY_RUN:
    print(f"DRY-RUN: would write {target} ({len(TEST)} bytes)")
    sys.exit(0)

if target.exists():
    bak = target.with_suffix(".py.bak")
    bak.write_bytes(target.read_bytes())
    print(f"  backup: {bak.name}")

target.write_text(TEST, encoding="utf-8")
print(f"  OK: {target}")
print()
print("Now run: python patch_gradio_cogvideox.py")
print("(it will create the adapter, then skip the existing test file)")