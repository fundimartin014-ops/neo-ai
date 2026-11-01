"""Rewind.ai adapter (bearer auth, async polling)."""
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
