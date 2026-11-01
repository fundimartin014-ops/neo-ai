"""Video router plugin. Exposes callable tools. Does NOT auto-register.
Wire into core.tool_registry in Phase 3 after verification.
"""
from skills.video_generate_skill import video_generate, video_generate_available


def install(registry):
    """Call from your tool loader once you are ready to expose these tools."""
    if hasattr(registry, "register"):
        registry.register("video_generate", video_generate)
        registry.register("video_available", video_generate_available)
    return True


__all__ = ["install", "video_generate", "video_generate_available"]
