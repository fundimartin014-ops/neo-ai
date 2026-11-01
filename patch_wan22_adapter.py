#!/usr/bin/env python3
"""patch_wan22_adapter.py -- Rewrite tier0_gradio.py for zerogpu-aoti/wan2-2.
Chain: prompt -> Pollinations T2I -> WAN 2.2 I2V -> local mp4.
"""
from pathlib import Path
import sys, ast
from urllib.parse import quote

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv

ADAPTER = '''"""WAN 2.2 adapter via zerogpu-aoti HF Space.

Two-step chain to support text-to-video on an image-to-video Space:
  1. Pollinations generates a still image from the prompt (free, no auth)
  2. WAN 2.2 Space animates the image (free, ZeroGPU)

If the caller supplies metadata.image_url, step 1 is skipped.
"""
import os, shutil, time
from pathlib import Path
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult

try:
    from gradio_client import Client, handle_file
except ImportError:
    Client = None
    handle_file = None


class Wan22Adapter(BaseVideoAdapter):
    name = "wan22-hf"
    SPACE = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"
    OUT_DIR = Path(__file__).parent.parent.parent / "generated_videos"
    POLLINATIONS = "https://image.pollinations.ai/prompt/{prompt}?width=1024&height=576&nologo=true&model=flux"

    def _image_url_for_prompt(self, prompt):
        """Build a Pollinations URL from the prompt (a valid image URL)."""
        return self.POLLINATIONS.format(prompt=quote(prompt, safe=""))

    def generate(self, req: VideoRequest) -> VideoResult:
        if Client is None:
            raise RuntimeError("gradio_client not installed: pip install gradio_client")

        start = time.time()

        # Step 1: resolve input image (skip if caller supplied one)
        image_url = (req.metadata or {}).get("image_url")
        if not image_url:
            image_url = self._image_url_for_prompt(req.prompt)
            print(f"  [wan22] step 1/2: generating reference image via Pollinations")
        else:
            print(f"  [wan22] step 1/2: using caller-supplied image_url")

        # Clamp duration to safe range (space defaults to 3.5s)
        duration = min(max(float(req.duration or 3.5), 1.0), 4.0)

        # Step 2: call the Space
        print(f"  [wan22] step 2/2: WAN 2.2 I2V (duration={duration}s, steps=6)")
        try:
            client = Client(self.SPACE, verbose=False)
        except Exception as e:
            raise RuntimeError(f"WAN 2.2 Space unavailable: {e}")

        try:
            result = client.predict(
                input_image=handle_file(image_url),
                prompt=req.prompt,
                steps=6,
                duration_seconds=duration,
                guidance_scale=1.0,
                guidance_scale_2=1.0,
                seed=42,
                randomize_seed=True,
                api_name="/generate_video",
            )
        except Exception as e:
            raise RuntimeError(f"WAN 2.2 predict failed: {e}")

        # Result: (generated_video_filepath, seed)
        video_path = None
        if isinstance(result, (tuple, list)) and len(result) >= 1:
            video_path = result[0]
        elif isinstance(result, str):
            video_path = result
        if not video_path:
            raise RuntimeError(f"no video path in result: {result}")

        src = Path(str(video_path))
        if not src.exists():
            raise RuntimeError(f"returned path does not exist: {src}")

        # Persist to project generated_videos/
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time())
        uid = (req.user_id or "anon").replace(" ", "_")[:32]
        dest = self.OUT_DIR / f"wan22_{stamp}_{uid}.mp4"
        shutil.copy2(src, dest)

        return VideoResult(
            url=str(dest),
            provider=self.name,
            model="wan-2.2-fp8",
            latency_ms=int((time.time() - start) * 1000),
        )

    def health_check(self) -> bool:
        if Client is None:
            return False
        try:
            Client(self.SPACE, verbose=False)
            return True
        except Exception:
            return False
'''

target = ROOT / "core/video_adapters/tier0_gradio.py"
if not target.exists():
    print(f"ERROR: {target} not found -- run patch_gradio_cogvideox.py first")
    sys.exit(1)

try:
    ast.parse(ADAPTER)
    print("  generated adapter parses OK")
except SyntaxError as e:
    print(f"ERROR: syntax in generated adapter: {e}"); sys.exit(1)

if DRY_RUN:
    print(f"DRY-RUN: would overwrite {target} ({len(ADAPTER)} bytes)")
    sys.exit(0)

bak = ROOT / "core/video_adapters/tier0_gradio.py.bak"
bak.write_bytes(target.read_bytes())
print(f"  backup: {bak.name}")
try:
    target.write_text(ADAPTER, encoding="utf-8")
    print(f"  OK: {target}")
except Exception as e:
    target.write_bytes(bak.read_bytes())
    print(f"  ROLLBACK: {e}"); sys.exit(1)
print()
print("Next: python test_gradio_cogvideox.py")
print("(script still works -- it calls the same class name)")