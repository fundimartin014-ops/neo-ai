"""Doubao2API adapter (client_session auth)."""
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
