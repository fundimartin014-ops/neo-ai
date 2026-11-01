"""Base adapter interface. Each provider subclasses this."""
from abc import ABC, abstractmethod
from ..video_request import VideoRequest, VideoResult


class BaseVideoAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, req: VideoRequest) -> VideoResult:
        """Synchronous generate. Raise on failure -- router handles fallback."""
        ...

    def health_check(self) -> bool:
        """Return True if provider looks healthy. Override per adapter."""
        return True
