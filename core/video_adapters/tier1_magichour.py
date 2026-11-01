"""Magic Hour adapter -- free-plan compatible with download persistence."""
import os, time, requests
from pathlib import Path
from ._base import BaseVideoAdapter
from ..video_request import VideoRequest, VideoResult


class MagicHourAdapter(BaseVideoAdapter):
    name = "magic-hour"
    BASE = os.getenv("MAGIC_HOUR_URL", "https://api.magichour.ai/v1")
    OUT_DIR = Path(__file__).parent.parent.parent / "generated_videos"

    def _headers(self):
        key = os.getenv("MAGIC_HOUR_API_KEY")
        if not key:
            raise RuntimeError("MAGIC_HOUR_API_KEY not set")
        return {"Authorization": f"Bearer {key}",
                "Content-Type": "application/json"}

    def check_account(self):
        r = requests.get(f"{self.BASE}/account",
                         headers=self._headers(), timeout=30)
        if r.status_code == 401:
            raise RuntimeError("Magic Hour: 401 -- bad API key")
        if r.status_code >= 400:
            raise RuntimeError(f"Magic Hour account {r.status_code}: {r.text[:300]}")
        return r.json()

    def _download(self, url, job_id):
        """Download signed URL to disk. Returns local path."""
        self.OUT_DIR.mkdir(parents=True, exist_ok=True)
        safe_id = "".join(c for c in job_id if c.isalnum() or c in "-_")[:32]
        out_path = self.OUT_DIR / f"magic_hour_{safe_id}.mp4"
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return out_path

    def generate(self, req: VideoRequest) -> VideoResult:
        headers = self._headers()
        try:
            account = self.check_account()
            balance = account.get("credits") or account.get("balance")
            if balance is not None:
                print(f"  [magic-hour] account balance: {balance} credits")
        except Exception as e:
            print(f"  [magic-hour] account check skipped: {e}")

        resolution = req.resolution or "480p"
        model = req.model_hint or "ltx-2.5"
        if resolution in ("720p", "1080p", "4k") and model in ("ltx-2.5", "minimax-h3"):
            print(f"  [magic-hour] WARNING: {resolution} requires a paid plan. "
                  f"Falling back to 480p for {model}.")
            resolution = "480p"

        payload = {
            "end_seconds": int(req.duration),
            "aspect_ratio": req.aspect_ratio,
            "resolution": resolution,
            "style": {"prompt": req.prompt},
            "model": model,
        }
        start = time.time()
        r = requests.post(f"{self.BASE}/text-to-video",
                          json=payload, headers=headers, timeout=60)
        if r.status_code == 401:
            raise RuntimeError("Magic Hour: 401 Unauthorized (bad API key)")
        if r.status_code == 402:
            raise RuntimeError(
                f"Magic Hour: 402 Payment Required.\n"
                f"  Requested: model={model}, resolution={resolution}, "
                f"duration={req.duration}s\n"
                f"  Response: {r.text[:500]}\n"
                f"  If balance is positive, this is a plan-gate. Check Billing."
            )
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

                # Download the expiring signed URL to permanent local storage
                try:
                    local = self._download(url, job_id)
                    print(f"  [magic-hour] downloaded to: {local}")
                    download_url = str(local)
                except Exception as e:
                    print(f"  [magic-hour] download failed, keeping signed URL: {e}")
                    download_url = url

                return VideoResult(
                    url=download_url, provider=self.name,
                    model=model, job_id=job_id,
                    latency_ms=int((time.time() - start) * 1000),
                )
            if status in ("error", "failed"):
                raise RuntimeError(f"Magic Hour: job {status}: {data}")
        raise TimeoutError(f"Magic Hour: job {job_id} timed out after 900s")

    def health_check(self) -> bool:
        return bool(os.getenv("MAGIC_HOUR_API_KEY"))
