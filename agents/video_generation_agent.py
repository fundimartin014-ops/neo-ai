"""Video generation agent. Standalone class -- not auto-registered."""
from skills.video_generate_skill import video_generate


class VideoGenerationAgent:
    name = "video_generation_agent"

    def handle(self, message: dict):
        prompt = message.get("prompt") or message.get("text") or ""
        if not prompt:
            return {"ok": False, "error": "no prompt"}
        result = video_generate(
            prompt=prompt,
            quality_tier=message.get("quality_tier", "standard"),
            user_id=message.get("user_id", ""),
            duration=message.get("duration", 5.0),
            aspect_ratio=message.get("aspect_ratio", "16:9"),
            resolution=message.get("resolution", "720p"),
            model_hint=message.get("model_hint"),
        )
        if hasattr(result, "url"):
            return {"ok": True, "url": result.url, "provider": result.provider,
                    "tier": result.tier, "model": result.model}
        return {"ok": False, "queued": True, "job_id": getattr(result, "job_id", None),
                "reason": getattr(result, "reason", "unknown")}
