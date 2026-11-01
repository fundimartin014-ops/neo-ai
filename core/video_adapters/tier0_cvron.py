"""CVRON API HUB adapter (no auth)."""
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
