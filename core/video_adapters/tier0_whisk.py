"""Whisk-API adapter (VEO 3.1 image-to-video, cookie auth)."""
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
