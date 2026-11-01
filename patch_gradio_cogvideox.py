#!/usr/bin/env python3
"""patch_gradio_cogvideox.py -- Add CogVideoX HF Space adapter + test."""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv
created, skipped, errors = [], [], []

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
        p.write_text(content, encoding="utf-8")
        created.append(rel); print(f"  OK: {rel}")
    except Exception as e:
        errors.append((rel, str(e))); print(f"  ERR: {rel}: {e}")

print("=" * 70)
print("patch_gradio_cogvideox.py")
print(f"  Root: {ROOT}")
print(f"  Mode: {'DRY-RUN' if DRY_RUN else 'SAFE'}")
print("=" * 70)

# ---------- 1. The adapter ----------
write_new("core/video_adapters/tier0_gradio.py", '''"""Gradio Space adapter -- free HF Spaces via gradio_client.

CogVideoX-2B: pure text-to-video, no auth, runs on ZeroGPU.
Queue times vary (10s to 5min). Free forever as long as Space exists.
"""
import shutil, time
from pathlib import Path
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult

try:
    from gradio_client import Client
except ImportError:
    Client = None


class CogVideoXAdapter(BaseVideoAdapter):
    name = "cogvideox-hf"
    SPACE = "zai-org/CogVideoX-2B-Space"
    OUT_DIR = Path(__file__).parent.parent.parent / "generated_videos"

    def generate(self, req: VideoRequest) -> VideoResult:
        if Client is None:
            raise RuntimeError("gradio_client not installed: pip install gradio_client")

        start = time.time()
        try:
            client = Client(self.SPACE)
        except Exception as e:
            raise RuntimeError(f"Space unavailable ({self.SPACE}): {e}")

        try:
            result = client.predict(
                prompt=req.prompt,
                num_inference_steps=50,
                guidance_scale=6.0,
                api_name="/generate",
            )
        except Exception as e:
            raise RuntimeError(f"Space predict failed: {e}")

        # Result shape per schema: (video_dict, download_video_path, download_gif_path)
        download_path = None
        if isinstance(result, (tuple, list)) and len(result) >= 2:
            download_path = result[1]
        elif isinstance(result, dict):
            download_path = result.get("video") or result.get("path")

        if not download_path:
            raise RuntimeError(f"no file path in result: {result}")

        src = Path(str(download_path))
        if not src.exists():
            raise RuntimeError(f"reported path does not exist: {src}")

        # Persist to project generated_videos/ so URL does not expire
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = self.OUT_DIR / f"cogvideox_{int(time.time())}_{req.user_id or 'anon'}.mp4"
        shutil.copy2(src, dest)

        return VideoResult(
            url=str(dest),
            provider=self.name,
            model="cogvideox-2b",
            latency_ms=int((time.time() - start) * 1000),
        )

    def health_check(self) -> bool:
        if Client is None:
            return False
        try:
            Client(self.SPACE)
            return True
        except Exception:
            return False
''')

# ---------- 2. The isolated test ----------
write_new("test_gradio_cogvideox.py", '''#!/usr/bin/env python3
"""Isolated test for CogVideoX HF Space. Uses zero API credits."""
import sys, time

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
print("  Calling Space... (do not close this window)\n")

try:
    result = CogVideoXAdapter().generate(req)
    print("\\n=== SUCCESS ===")
    print(f"  Provider: {result.provider}")
    print(f"  Model:    {result.model}")
    print(f"  Latency:  {result.latency_ms} ms")
    print(f"  File:     {result.url}")
    import os
    size = os.path.getsize(result.url)
    print(f"  Size:     {size:,} bytes")
except Exception as e:
    print(f"\\n=== FAILED ===")
    print(f"  {type(e).__name__}: {e}")
    sys.exit(2)
''')

# ---------- summary ----------
print()
print("=" * 70)
print(f"SUMMARY: created={len(created)} skipped={len(skipped)} errors={len(errors)}")
if created: print("  Created:", ", ".join(created))
if skipped: print("  Skipped:", ", ".join(skipped))
if errors:
    print("  ERRORS:")
    for p, e in errors: print(f"    {p}: {e}")
    sys.exit(1)
print("=" * 70)
if not DRY_RUN:
    print("Next: python test_gradio_cogvideox.py")
    print("If SUCCESS, we add it to video_providers.yaml in Phase 3.")
print()