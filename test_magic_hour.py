#!/usr/bin/env python3
"""test_magic_hour.py -- isolated end-to-end test for Magic Hour adapter.
Reads MAGIC_HOUR_API_KEY from .env in the project root only.
"""
import os, sys
from pathlib import Path

# ---- Load .env (simple parser, no extra deps) ----
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")
else:
    print(f"ERROR: .env not found at {env_file}")
    sys.exit(1)

# ---- Check key ----
key = os.getenv("MAGIC_HOUR_API_KEY", "").strip()
if not key or key == "mhk_live_your_NEW_key_here":
    print("ERROR: MAGIC_HOUR_API_KEY not set in .env")
    print(f"  Edit {env_file} and add a line:")
    print("    MAGIC_HOUR_API_KEY=mhk_live_your_real_NEW_key")
    sys.exit(1)

print(f"  API key loaded from .env: {key[:10]}...{key[-4:]}  (len={len(key)})")
print("  Calling Magic Hour text-to-video (5s, 720p, 16:9)...")
print("  Expect 30-90 seconds. This uses real credits.\n")

# ---- Import + run ----
from core.video_request import VideoRequest
from core.video_adapters.tier1_magichour import MagicHourAdapter

req = VideoRequest(
    prompt="a sunset over mountains, cinematic, slow camera move",
    duration=5.0,
    aspect_ratio="16:9",
    resolution="720p",
    user_id="magic-hour-test",
)

try:
    result = MagicHourAdapter().generate(req)
    print("\n=== SUCCESS ===")
    print(f"  Provider: {result.provider}")
    print(f"  Model:    {result.model}")
    print(f"  Job ID:   {result.job_id}")
    print(f"  Latency:  {result.latency_ms} ms")
    print(f"  URL:      {result.url}")
except Exception as e:
    print("\n=== FAILED ===")
    print(f"  {type(e).__name__}: {e}")
    sys.exit(2)