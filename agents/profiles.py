"""Agent profiles — restrict which aliases are exposed based on env or config.

Profile resolution order:
  1. NEO_AGENT_PROFILE env var
  2. config/agent_profiles.json -> active_profile
  3. "all"
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("agents.profiles")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "agent_profiles.json"
_DEFAULT_PROFILE = "all"


@lru_cache(maxsize=1)
def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        logger.warning("[profiles] config missing at %s; defaulting to 'all'", _CONFIG_PATH)
        return {"profiles": {"all": {"agents": ["*"]}}, "active_profile": "all"}
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("[profiles] config parse failed: %s; defaulting to 'all'", e)
        return {"profiles": {"all": {"agents": ["*"]}}, "active_profile": "all"}


def active_profile() -> str:
    env = (os.getenv("NEO_AGENT_PROFILE") or "").strip()
    if env:
        return env
    return _load_config().get("active_profile", _DEFAULT_PROFILE)


def allowed_aliases() -> set[str] | None:
    """Allowed aliases as a set, or None if everything is allowed."""
    profile = active_profile()
    cfg = _load_config()
    profiles = cfg.get("profiles", {})
    if profile not in profiles:
        logger.warning("[profiles] unknown profile %r, falling back to 'all'", profile)
        profile = _DEFAULT_PROFILE
        if profile not in profiles:
            return None
    agents = profiles[profile].get("agents", [])
    if "*" in agents:
        return None
    return set(agents)


def is_allowed(alias: str) -> bool:
    allowed = allowed_aliases()
    if allowed is None:
        return True
    return alias in allowed


def describe() -> str:
    profile = active_profile()
    allowed = allowed_aliases()
    if allowed is None:
        return f"profile='{profile}' (all aliases allowed)"
    return f"profile='{profile}' ({len(allowed)} aliases: {', '.join(sorted(allowed))})"


def reload() -> None:
    _load_config.cache_clear()
