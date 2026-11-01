#!/usr/bin/env python3
"""patch_video_router_v1.py -- Phase 1: CREATE video router skeleton.
Creates ONLY new files. NEVER modifies existing files. Idempotent.
Run with --dry-run to preview. Run with --force to overwrite existing.
"""
from pathlib import Path
import sys, ast

ROOT = Path(__file__).parent.resolve()
DRY_RUN = "--dry-run" in sys.argv
FORCE   = "--force"   in sys.argv
created, skipped, errors = [], [], []

def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and not FORCE:
        skipped.append(rel); print(f"  SKIP (exists): {rel}"); return
    if rel.endswith(".py"):
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append((rel, e)); print(f"  SYNTAX ERROR in generated code: {rel}: {e}"); return
    if DRY_RUN:
        created.append(rel); print(f"  DRY-RUN would create: {rel}"); return
    try:
        p.write_text(content, encoding="utf-8")
        created.append(rel); print(f"  OK: {rel}")
    except Exception as e:
        errors.append((rel, e)); print(f"  ERR: {rel} -> {e}")

print("=" * 70)
print("patch_video_router_v1.py -- Phase 1 skeleton")
print(f"  Root: {ROOT}")
print(f"  Mode: {'DRY-RUN' if DRY_RUN else ('FORCE' if FORCE else 'SAFE (skip existing)')}")
print("=" * 70)

# ---------------------------------------------------------------
write("core/video_request.py", '''"""Video request/result dataclasses. Phase 1 skeleton."""
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
''')

# ---------------------------------------------------------------
write("core/video_adapters/__init__.py", '''"""Video provider adapters. Each adapter wraps one provider."""
''')

# ---------------------------------------------------------------
write("core/video_adapters/_base.py", '''"""Base adapter interface. Each provider subclasses this."""
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
''')

# ---------------------------------------------------------------
write("core/video_adapters/tier0_proxy.py", '''"""Adapter for Free-Multimodal-Proxy (OpenAI-compatible, no auth).
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
''')

# ---------------------------------------------------------------
write("core/video_providers.py", '''"""Provider registry loader from config/video_providers.yaml.
Requires pyyaml (already in requirements.txt).
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class Provider:
    name: str
    tier: int
    endpoint: str
    auth: str
    models: List[str]
    daily_quota: Optional[int] = None
    monthly_budget_usd: Optional[float] = None
    per_user_daily_cap: int = 5
    reliability: float = 0.5
    enabled_flag: str = "TIER0_ENABLED"
    adapter: str = ""
    _used_today: int = 0
    _day: Optional[str] = None

    def is_enabled(self) -> bool:
        return os.getenv(self.enabled_flag, "false").lower() in ("1", "true", "yes")

    def quota_ok(self) -> bool:
        if self.daily_quota is None:
            return True
        self._roll_day()
        return self._used_today < self.daily_quota

    def record_use(self) -> None:
        self._roll_day()
        self._used_today += 1

    def _roll_day(self) -> None:
        today = date.today().isoformat()
        if self._day != today:
            self._day = today
            self._used_today = 0


def load_providers(yaml_path: str) -> List[Provider]:
    if yaml is None:
        raise RuntimeError("pyyaml not installed: pip install pyyaml")
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    providers = []
    for entry in data.get("providers", []):
        providers.append(Provider(
            name=entry["name"],
            tier=int(entry["tier"]),
            endpoint=entry.get("endpoint", ""),
            auth=entry.get("auth", "none"),
            models=list(entry.get("models", [])),
            daily_quota=entry.get("daily_quota"),
            monthly_budget_usd=entry.get("monthly_budget_usd"),
            per_user_daily_cap=int(entry.get("per_user_daily_cap", 5)),
            reliability=float(entry.get("reliability", 0.5)),
            enabled_flag=entry.get("enabled_flag", "TIER0_ENABLED"),
            adapter=entry.get("adapter", ""),
        ))
    return providers
''')

# ---------------------------------------------------------------
write("core/video_audit.py", '''"""Structured audit log for video generation. Appends JSONL."""
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
            f.write(json.dumps(asdict(record)) + "\\n")
    except Exception:
        pass
''')

# ---------------------------------------------------------------
write("core/video_router.py", '''"""Tier-aware video router. Never touches existing code."""
import time, logging
from typing import List, Dict, Any

from .video_request import VideoRequest, VideoResult, QueuedJob
from .video_providers import Provider, load_providers
from .video_audit import log_audit, AuditRecord

log = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, threshold=10, open_duration=900):
        self.threshold = threshold
        self.open_duration = open_duration
        self._state: Dict[str, Dict[str, Any]] = {}

    def is_open(self, name: str) -> bool:
        s = self._state.get(name)
        if not s: return False
        if s["state"] == "OPEN":
            if time.time() - s["opened_at"] > self.open_duration:
                s["state"] = "HALF_OPEN"; return False
            return True
        return False

    def record_success(self, name: str) -> None:
        self._state[name] = {"state": "CLOSED", "failures": 0, "opened_at": 0}

    def record_failure(self, name: str) -> None:
        s = self._state.setdefault(name, {"state": "CLOSED", "failures": 0, "opened_at": 0})
        s["failures"] += 1
        if s["failures"] >= self.threshold:
            s["state"] = "OPEN"; s["opened_at"] = time.time()


def _load_adapter(provider: Provider):
    if provider.adapter == "tier0_proxy":
        from .video_adapters.tier0_proxy import FreeMultimodalProxyAdapter
        return FreeMultimodalProxyAdapter()
    return None


class VideoRouter:
    def __init__(self, providers: List[Provider], adapters: Dict[str, Any]):
        self.providers = providers
        self.adapters = adapters
        self.breaker = CircuitBreaker()

    @classmethod
    def from_config(cls, yaml_path: str) -> "VideoRouter":
        providers = load_providers(yaml_path)
        adapters = {}
        for p in providers:
            try:
                a = _load_adapter(p)
                if a: adapters[p.name] = a
            except Exception as e:
                log.warning(f"adapter load failed for {p.name}: {e}")
        return cls(providers, adapters)

    def route(self, req: VideoRequest):
        tiers = [0, 1] if req.quality_tier == "standard" else [2]
        for tier in tiers:
            for p in sorted(
                [x for x in self.providers if x.tier == tier],
                key=lambda x: x.reliability, reverse=True,
            ):
                if not p.is_enabled():                              continue
                if self.breaker.is_open(p.name):                    continue
                if not p.quota_ok():                                continue
                if req.model_hint and req.model_hint not in p.models: continue
                adapter = self.adapters.get(p.name)
                if adapter is None:                                 continue
                start = time.time()
                try:
                    result = adapter.generate(req)
                    latency = int((time.time() - start) * 1000)
                    result.latency_ms = latency
                    result.tier = p.tier
                    self.breaker.record_success(p.name)
                    p.record_use()
                    log_audit(AuditRecord(
                        ts=time.time(), user_id=req.user_id, tier=p.tier,
                        provider=p.name, model=result.model, latency_ms=latency,
                        cost_usd=result.cost_usd, success=True,
                    ))
                    return result
                except Exception as e:
                    log.warning(f"provider {p.name} failed: {e}")
                    self.breaker.record_failure(p.name)
                    log_audit(AuditRecord(
                        ts=time.time(), user_id=req.user_id, tier=p.tier,
                        provider=p.name, model=req.model_hint or "?",
                        latency_ms=int((time.time() - start) * 1000),
                        cost_usd=0.0, success=False, error=str(e)[:200],
                    ))
                    continue
        return QueuedJob(job_id=f"queued_{int(time.time())}",
                        reason="all_tiers_exhausted", estimated_wait_seconds=120)
''')

# ---------------------------------------------------------------
write("config/video_providers.yaml", '''# Video provider registry. Phase 1 -- minimal set.
# Enable with env vars: TIER0_ENABLED=true, TIER1_ENABLED=true
providers:
  # ---------- TIER 0: GREY / UNOFFICIAL ----------
  - name: free-multimodal-proxy
    tier: 0
    endpoint: http://localhost:8080/v1/videos/generations
    auth: none
    adapter: tier0_proxy
    models: [wan-2.2, kling-3.0, seedance-2.0, pixverse-v6, hailuo]
    daily_quota: null
    per_user_daily_cap: 5
    reliability: 0.70
    enabled_flag: TIER0_ENABLED

  # ---------- TIER 1: OFFICIAL FREE TIERS ----------
  # Adapters not yet implemented -- router skips these cleanly.
  - name: magic-hour
    tier: 1
    endpoint: https://api.magichour.ai/v1
    auth: bearer:MAGIC_HOUR_API_KEY
    adapter: ""
    models: [ltx-2.5, wan-2.2, minimax-h3]
    daily_quota: 90
    per_user_daily_cap: 3
    reliability: 0.99
    enabled_flag: TIER1_ENABLED

  - name: agnes-ai
    tier: 1
    endpoint: https://api.agnes.ai/v1
    auth: bearer:AGNES_API_KEY
    adapter: ""
    models: [agnes-video-v2.0]
    daily_quota: null
    per_user_daily_cap: 5
    reliability: 0.85
    enabled_flag: TIER1_ENABLED

  # ---------- TIER 2: PAID (DORMANT) ----------
  - name: higgsfield
    tier: 2
    endpoint: https://platform.higgsfield.ai/v1
    auth: bearer:HF_KEY
    adapter: ""
    models: [seedance-2.5, kling-3.0]
    reliability: 0.99
    enabled_flag: PAID_ENABLED
''')

# ---------------------------------------------------------------
write("skills/video_generate_skill.py", '''"""Video generation skill -- thin wrapper over VideoRouter.
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
''')

# ---------------------------------------------------------------
print()
print("=" * 70)
print(f"SUMMARY: created={len(created)}  skipped={len(skipped)}  errors={len(errors)}")
if created:  print("  Created:", ", ".join(created))
if skipped:  print("  Skipped:", ", ".join(skipped))
if errors:
    print("  ERRORS:")
    for p, e in errors: print(f"    {p}: {e}")
    sys.exit(1)
print("=" * 70)
if not DRY_RUN:
    print("Next steps:")
    print("  1. $env:TIER0_ENABLED = 'true'")
    print("  2. $env:TIER1_ENABLED = 'true'")
    print("  3. python -c 'from skills.video_generate_skill import video_generate; print(video_generate(\"test\", user_id=\"u1\"))'")
    print("  4. If Free-Multimodal-Proxy not running, router will queue -- that is correct Phase 1 behavior.")
print()