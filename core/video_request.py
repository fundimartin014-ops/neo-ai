"""Video request/result dataclasses. Phase 1 skeleton."""
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any


@dataclass
class VideoRequest:
    prompt: str
    duration: float = 5.0
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    quality_tier: Literal["standard", "premium"] = "standard"
    user_id: str = ""
    model_hint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoResult:
    url: str
    provider: str
    model: str
    tier: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    job_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueuedJob:
    job_id: str
    reason: str
    estimated_wait_seconds: int = 60
