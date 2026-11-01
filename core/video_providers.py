"""Provider registry loader from config/video_providers.yaml.
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
