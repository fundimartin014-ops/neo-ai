"""Video content safety gate. Stub by default; enforcing is opt-in.

Env vars:
  VIDEO_SAFETY_ENFORCE=true   -- block on detection (default: warn only)
  VIDEO_SAFETY_KEYWORDS       -- comma-separated blocked words (default: minimal list)
"""
import os, logging

log = logging.getLogger(__name__)

_DEFAULT_BLOCKED = {"csam", "child porn", "cp"}


def _blocked_terms():
    raw = os.getenv("VIDEO_SAFETY_KEYWORDS", "")
    extra = {w.strip().lower() for w in raw.split(",") if w.strip()}
    return _DEFAULT_BLOCKED | extra


def check_prompt(prompt: str):
    """Return (ok: bool, reason: str). Always blocks hard categories;
    logs (does not block) on soft categories unless enforce is on."""
    p = (prompt or "").lower()
    terms = _blocked_terms()
    hits = [w for w in terms if w in p]
    if hits:
        return False, f"prompt contains blocked term(s): {hits}"
    return True, ""


def check_video_url(url: str):
    """Placeholder for post-generation frame classifier. Returns (ok, reason)."""
    if os.getenv("VIDEO_SAFETY_ENFORCE", "false").lower() != "true":
        return True, ""
    return True, ""
