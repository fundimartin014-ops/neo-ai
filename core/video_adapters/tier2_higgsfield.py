"""Higgsfield adapter (bearer auth, paid -- dormant)."""
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
