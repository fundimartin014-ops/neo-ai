"""Vercel AI Gateway adapter (bearer auth)."""
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
