#!/usr/bin/env python3
# Test WAN 2.2 via Pollinations + HF Space (free, no credits).
import sys, os

print("=" * 60)
print("WAN 2.2 HF Space test -- free, no credits used")
print("=" * 60)
print("Pipeline: prompt -> Pollinations image -> WAN 2.2 I2V")
print("Expected time: 30s - 5min (ZeroGPU queue)")
print()

from core.video_request import VideoRequest
from core.video_adapters.tier0_gradio import Wan22Adapter

req = VideoRequest(
    prompt="a cat running in slow motion, cinematic lighting",
    duration=3.5,
    user_id="wan22-test",
)

print(f"  Prompt: {req.prompt}")
print("  Calling pipeline... (do not close this window)")
print()

try:
    result = Wan22Adapter().generate(req)
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