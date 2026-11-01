"""Jimeng Free API adapter (session_id auth)."""
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
