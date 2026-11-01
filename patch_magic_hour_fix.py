#!/usr/bin/env python3
"""patch_magic_hour_fix.py -- Rewrite Magic Hour adapter with proper polling.
Backs up the existing adapter. Rolls back on failure.
"""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv
errors = []

ADAPTER = '''"""Magic Hour adapter with async job polling. Free tier compatible."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class MagicHourAdapter(BaseVideoAdapter):
    name = "magic-hour"
    BASE = os.getenv("MAGIC_HOUR_URL", "https://api.magichour.ai/v1")

    def _headers(self):
        key = os.getenv("MAGIC_HOUR_API_KEY")
        if not key:
            raise RuntimeError("MAGIC_HOUR_API_KEY not set")
        return {"Authorization": f"Bearer {key}",
                "Content-Type": "application/json"}

    def generate(self, req: VideoRequest) -> VideoResult:
        headers = self._headers()
        payload = {
            "end_seconds": int(req.duration),
            "aspect_ratio": req.aspect_ratio,
            "resolution": req.resolution,
            "style": {"prompt": req.prompt},
            "model": req.model_hint or "ltx-2.5",
        }
        start = time.time()
        r = requests.post(f"{self.BASE}/text-to-video",
                          json=payload, headers=headers, timeout=60)
        if r.status_code == 401:
            raise RuntimeError("Magic Hour: 401 Unauthorized (bad API key)")
        if r.status_code == 402:
            raise RuntimeError("Magic Hour: 402 Payment Required (out of credits)")
        if r.status_code >= 400:
            raise RuntimeError(f"Magic Hour create {r.status_code}: {r.text[:300]}")
        job = r.json()
        job_id = job.get("id")
        if not job_id:
            raise RuntimeError(f"Magic Hour: no job id in response: {job}")

        deadline = time.time() + 900
        while time.time() < deadline:
            time.sleep(5)
            p = requests.get(f"{self.BASE}/video-projects/{job_id}",
                             headers=headers, timeout=30)
            if p.status_code >= 400:
                continue
            data = p.json()
            status = data.get("status")
            if status == "complete":
                downloads = data.get("downloads") or []
                if not downloads:
                    raise RuntimeError(f"Magic Hour: complete but no downloads: {data}")
                url = downloads[0].get("url")
                if not url:
                    raise RuntimeError(f"Magic Hour: no url in downloads: {downloads}")
                return VideoResult(
                    url=url, provider=self.name,
                    model=payload["model"], job_id=job_id,
                    latency_ms=int((time.time() - start) * 1000),
                )
            if status in ("error", "failed"):
                raise RuntimeError(f"Magic Hour: job {status}: {data}")
        raise TimeoutError(f"Magic Hour: job {job_id} timed out after 900s")

    def health_check(self) -> bool:
        return bool(os.getenv("MAGIC_HOUR_API_KEY"))
'''

target = ROOT / "core/video_adapters/tier1_magichour.py"
if not target.exists():
    print(f"ERROR: {target} not found -- run Phase 2a first")
    sys.exit(1)

try:
    ast.parse(ADAPTER)
except SyntaxError as e:
    print(f"ERROR: new adapter has syntax error: {e}")
    sys.exit(1)

if DRY_RUN:
    print(f"DRY-RUN: would overwrite {target}")
    print(f"  current size: {target.stat().st_size} bytes")
    print(f"  new size:     {len(ADAPTER)} bytes")
    sys.exit(0)

bak = ROOT / "core/video_adapters/tier1_magichour.py.bak"
bak.write_bytes(target.read_bytes())
print(f"  backup: {bak.name}")
try:
    target.write_text(ADAPTER, encoding="utf-8")
    print(f"  OK: {target}")
except Exception as e:
    target.write_bytes(bak.read_bytes())
    print(f"  ROLLBACK: {e}")
    sys.exit(1)
print()
print("Adapter rewritten with polling. Next: run the isolated test.")