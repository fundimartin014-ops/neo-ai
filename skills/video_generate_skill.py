"""Video generation skill -- thin wrapper over VideoRouter.
Usage from an agent or chat:
    from skills.video_generate_skill import video_generate
    result = video_generate("a cat running", quality_tier="standard")
"""
from pathlib import Path

_router = None


def _get_router():
    global _router
    if _router is None:
        from core.video_router import VideoRouter
        cfg = Path(__file__).parent.parent / "config" / "video_providers.yaml"
        _router = VideoRouter.from_config(str(cfg))
    return _router


def video_generate(prompt: str, quality_tier: str = "standard",
                   user_id: str = "", **kwargs):
    """Generate a video via the tier router. Returns VideoResult or QueuedJob."""
    from core.video_request import VideoRequest
    req = VideoRequest(
        prompt=prompt,
        duration=kwargs.get("duration", 5.0),
        aspect_ratio=kwargs.get("aspect_ratio", "16:9"),
        resolution=kwargs.get("resolution", "720p"),
        quality_tier=quality_tier,
        user_id=user_id,
        model_hint=kwargs.get("model_hint"),
    )
    return _get_router().route(req)


def video_generate_available() -> bool:
    """Quick health check -- returns True if at least one provider is enabled."""
    import os
    return any(os.getenv(f, "false").lower() in ("1", "true", "yes")
               for f in ("TIER0_ENABLED", "TIER1_ENABLED", "PAID_ENABLED"))
