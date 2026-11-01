"""Adapter for Free-Multimodal-Proxy (OpenAI-compatible, no auth).
Expected running at http://localhost:8080 with /v1/videos/generations endpoint.
"""
import os, time, requests
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class FreeMultimodalProxyAdapter(BaseVideoAdapter):
    name = "free-multimodal-proxy"
    ENDPOINT = os.getenv(
        "FREE_MULTIMODAL_PROXY_URL",
        "http://localhost:8080/v1/videos/generations",
    )

    def generate(self, req: VideoRequest) -> VideoResult:
        model = req.model_hint or "wan-2.2"
        payload = {
            "model": model,
            "prompt": req.prompt,
            "duration": req.duration,
            "aspect_ratio": req.aspect_ratio,
            "resolution": req.resolution,
        }
        start = time.time()
        r = requests.post(self.ENDPOINT, json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        url = data.get("url") or data.get("data", [{}])[0].get("url")
        if not url:
            raise RuntimeError(f"no url in response: {data}")
        return VideoResult(
            url=url,
            provider=self.name,
            model=model,
            latency_ms=int((time.time() - start) * 1000),
        )

    def health_check(self) -> bool:
        try:
            base = self.ENDPOINT.rsplit("/videos/generations", 1)[0]
            return requests.get(base + "/models", timeout=5).status_code < 500
        except Exception:
            return False
