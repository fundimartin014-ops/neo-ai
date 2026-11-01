"""Structured audit log for video generation. Appends JSONL."""
import json, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


LOG_PATH = Path(__file__).parent.parent / "data" / "video_audit.jsonl"


@dataclass
class AuditRecord:
    ts: float
    user_id: str
    tier: int
    provider: str
    model: str
    latency_ms: int
    cost_usd: float
    success: bool
    error: Optional[str] = None


def log_audit(record: AuditRecord) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")
    except Exception:
        pass
