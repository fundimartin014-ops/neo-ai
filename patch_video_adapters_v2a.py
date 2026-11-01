#!/usr/bin/env python3
"""patch_video_adapters_v2a.py -- Phase 2a: CREATE 9 provider adapters.
Creates ONLY new files. NEVER modifies existing. Idempotent.
"""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv
FORCE   = "--force"   in sys.argv
created, skipped, errors = [], [], []

def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and not FORCE:
        skipped.append(rel); print(f"  SKIP (exists): {rel}"); return
    if rel.endswith(".py"):
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append((rel, e)); print(f"  SYNTAX ERROR: {rel}: {e}"); return
    if DRY_RUN:
        created.append(rel); print(f"  DRY-RUN would create: {rel}"); return
    try:
        p.write_text(content, encoding="utf-8")
        created.append(rel); print(f"  OK: {rel}")
    except Exception as e:
        errors.append((rel, e)); print(f"  ERR: {rel} -> {e}")

print("=" * 70)
print("patch_video_adapters_v2a.py -- Phase 2a")
print(f"  Root: {ROOT}")
print(f"  Mode: {'DRY-RUN' if DRY_RUN else ('FORCE' if FORCE else 'SAFE')}")
print("=" * 70)

# ---------------------------------------------------------------
write("core/video_adapters/tier0_jimeng.py", '''"""Jimeng Free API adapter (session_id auth)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class JimengAdapter(BaseVideoAdapter):
    name = "jimeng-free-api"
    ENDPOINT = os.getenv("JIMENG_URL", "http://localhost:8081/v1/videos/generations")

    def generate(self, req: VideoRequest) -> VideoResult:
        sid = os.getenv("JIMENG_SESSION_ID")
        if not sid:
            raise RuntimeError("JIMENG_SESSION_ID not set")
        headers = {"Authorization": f"Bearer {sid}", "Content-Type": "application/json"}
        payload = {
            "model": req.model_hint or "seedance-2.0",
            "prompt": req.prompt,
            "duration": req.duration,
            "aspect_ratio": req.aspect_ratio,
        }
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, headers=headers, timeout=300)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("data", [{}])[0].get("url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name,
                          model=payload["model"],
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return bool(os.getenv("JIMENG_SESSION_ID"))
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier0_prezzy.py", '''"""Prezzy / PrexzyAPIs adapter (no auth)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class PrezzyAdapter(BaseVideoAdapter):
    name = "prezzy-prexzyapis"
    ENDPOINT = os.getenv("PREZZY_URL", "https://prexzyapis.com/v1/videos/generations")

    def generate(self, req: VideoRequest) -> VideoResult:
        model = req.model_hint or "wan-2.2"
        payload = {
            "model": model, "prompt": req.prompt,
            "duration": req.duration, "aspect_ratio": req.aspect_ratio,
        }
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("data", [{}])[0].get("url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name, model=model,
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return True
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier0_cvron.py", '''"""CVRON API HUB adapter (no auth)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class CvronAdapter(BaseVideoAdapter):
    name = "cvron-hub"
    ENDPOINT = os.getenv("CVRON_URL", "https://api.cvron.dev/v1/videos")

    def generate(self, req: VideoRequest) -> VideoResult:
        model = req.model_hint or "wan-2.2"
        payload = {
            "model": model, "prompt": req.prompt,
            "duration": req.duration, "aspect_ratio": req.aspect_ratio,
        }
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("data", [{}])[0].get("url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name, model=model,
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return True
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier0_doubao.py", '''"""Doubao2API adapter (client_session auth)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class DoubaoAdapter(BaseVideoAdapter):
    name = "doubao2api"
    ENDPOINT = os.getenv("DOUBAO_URL", "http://localhost:8082/v1/videos/generations")

    def generate(self, req: VideoRequest) -> VideoResult:
        session = os.getenv("DOUBAO_CLIENT_SESSION")
        if not session:
            raise RuntimeError("DOUBAO_CLIENT_SESSION not set")
        headers = {"Authorization": f"Bearer {session}", "Content-Type": "application/json"}
        model = req.model_hint or "doubao-video"
        payload = {"model": model, "prompt": req.prompt,
                   "duration": req.duration, "aspect_ratio": req.aspect_ratio}
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, headers=headers, timeout=300)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("data", [{}])[0].get("url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name, model=model,
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return bool(os.getenv("DOUBAO_CLIENT_SESSION"))
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier0_whisk.py", '''"""Whisk-API adapter (VEO 3.1 image-to-video, cookie auth)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class WhiskAdapter(BaseVideoAdapter):
    name = "whisk-api"
    ENDPOINT = os.getenv("WHISK_URL", "http://localhost:8083/v1/animate")

    def generate(self, req: VideoRequest) -> VideoResult:
        cookie = os.getenv("WHISK_COOKIE")
        if not cookie:
            raise RuntimeError("WHISK_COOKIE not set")
        image_url = req.metadata.get("image_url")
        if not image_url:
            raise RuntimeError("whisk requires metadata.image_url (image-to-video only)")
        headers = {"Cookie": cookie, "Content-Type": "application/json"}
        payload = {"image_url": image_url, "prompt": req.prompt}
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, headers=headers, timeout=300)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("video_url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name, model="veo-3.1",
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return bool(os.getenv("WHISK_COOKIE"))
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier1_magichour.py", '''"""Magic Hour adapter (bearer auth, per their SDK shape)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class MagicHourAdapter(BaseVideoAdapter):
    name = "magic-hour"
    ENDPOINT = "https://api.magichour.ai/v1/text-to-video"

    def generate(self, req: VideoRequest) -> VideoResult:
        api_key = os.getenv("MAGIC_HOUR_API_KEY")
        if not api_key:
            raise RuntimeError("MAGIC_HOUR_API_KEY not set")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "end_seconds": req.duration,
            "aspect_ratio": req.aspect_ratio,
            "resolution": req.resolution,
            "style": {"prompt": req.prompt},
        }
        if req.model_hint:
            payload["model"] = req.model_hint
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, headers=headers, timeout=600)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("download", {}).get("url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name,
                          model=req.model_hint or "default",
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return bool(os.getenv("MAGIC_HOUR_API_KEY"))
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier1_agnes.py", '''"""Agnes AI adapter (bearer auth, unlimited free)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class AgnesAdapter(BaseVideoAdapter):
    name = "agnes-ai"
    ENDPOINT = os.getenv("AGNES_URL", "https://api.agnes.ai/v1/videos/generations")

    def generate(self, req: VideoRequest) -> VideoResult:
        api_key = os.getenv("AGNES_API_KEY")
        if not api_key:
            raise RuntimeError("AGNES_API_KEY not set")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        model = req.model_hint or "agnes-video-v2.0"
        payload = {"model": model, "prompt": req.prompt,
                   "duration": req.duration, "aspect_ratio": req.aspect_ratio,
                   "resolution": req.resolution}
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, headers=headers, timeout=600)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("data", [{}])[0].get("url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name, model=model,
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return bool(os.getenv("AGNES_API_KEY"))
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier1_vercel.py", '''"""Vercel AI Gateway adapter (bearer auth)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class VercelAdapter(BaseVideoAdapter):
    name = "vercel-gateway"
    ENDPOINT = os.getenv("VERCEL_URL", "https://ai-gateway.vercel.sh/v1/videos/generations")

    def generate(self, req: VideoRequest) -> VideoResult:
        api_key = os.getenv("VERCEL_AI_KEY")
        if not api_key:
            raise RuntimeError("VERCEL_AI_KEY not set")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        model = req.model_hint or "wan-v3.0"
        payload = {"model": model, "prompt": req.prompt,
                   "duration": req.duration, "aspect_ratio": req.aspect_ratio}
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, headers=headers, timeout=600)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("data", [{}])[0].get("url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name, model=model,
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return bool(os.getenv("VERCEL_AI_KEY"))
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier1_rewind.py", '''"""Rewind.ai adapter (bearer auth, async polling)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class RewindAdapter(BaseVideoAdapter):
    name = "rewind-ai"
    BASE = os.getenv("REWIND_URL", "https://api.rewind.ai/v1")

    def generate(self, req: VideoRequest) -> VideoResult:
        api_key = os.getenv("REWIND_KEY")
        if not api_key:
            raise RuntimeError("REWIND_KEY not set")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        model = req.model_hint or "bytedance/seedance-1-5-pro"
        payload = {"model": model, "prompt": req.prompt,
                   "duration": f"{int(req.duration)}s", "aspectRatio": req.aspect_ratio}
        start = time.time()
        r = requests.post(f"{self.BASE}/videos/generate-async",
                         json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        job_id = r.json().get("jobId") or r.json().get("id")
        if not job_id:
            raise RuntimeError(f"no jobId: {r.json()}")
        deadline = time.time() + 600
        while time.time() < deadline:
            time.sleep(5)
            s = requests.get(f"{self.BASE}/jobs/{job_id}", headers=headers, timeout=30)
            s.raise_for_status()
            j = s.json()
            if j.get("status") == "completed":
                url = j.get("url") or j.get("output", {}).get("url")
                if not url:
                    raise RuntimeError(f"no url in job: {j}")
                return VideoResult(url=url, provider=self.name, model=model,
                                  job_id=job_id,
                                  latency_ms=int((time.time() - start) * 1000))
            if j.get("status") == "failed":
                raise RuntimeError(f"job failed: {j}")
        raise TimeoutError(f"rewind job {job_id} timed out")

    def health_check(self) -> bool:
        return bool(os.getenv("REWIND_KEY"))
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier2_higgsfield.py", '''"""Higgsfield adapter (bearer auth, paid -- dormant)."""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class HiggsfieldAdapter(BaseVideoAdapter):
    name = "higgsfield"
    ENDPOINT = os.getenv("HIGGSFIELD_URL", "https://platform.higgsfield.ai/v1/videos/generations")

    def generate(self, req: VideoRequest) -> VideoResult:
        key = os.getenv("HF_KEY")
        if not key:
            raise RuntimeError("HF_KEY not set")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        model = req.model_hint or "seedance-2.5"
        payload = {"model": model, "prompt": req.prompt,
                   "duration": req.duration, "aspect_ratio": req.aspect_ratio}
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, headers=headers, timeout=600)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("output", {}).get("url")
        if not url:
            raise RuntimeError(f"no url: {data}")
        return VideoResult(url=url, provider=self.name, model=model,
                          latency_ms=int((time.time() - start) * 1000))

    def health_check(self) -> bool:
        return bool(os.getenv("HF_KEY"))
''')

# ---------------------------------------------------------------
print()
print("=" * 70)
print(f"SUMMARY: created={len(created)}  skipped={len(skipped)}  errors={len(errors)}")
if created: print("  Created:", ", ".join(created))
if skipped: print("  Skipped:", ", ".join(skipped))
if errors:
    print("  ERRORS:")
    for p, e in errors: print(f"    {p}: {e}")
    sys.exit(1)
print("=" * 70)
if not DRY_RUN:
    print("Next: Phase 2b will update config/video_providers.yaml to map")
    print("      these adapters, and add safety + plugin + agent. Do NOT run")
    print("      Phase 2b until you run --dry-run for it and read the output.")
print()