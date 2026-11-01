"""Smart env loader.

Order:
  1. <project_root>/.env
  2. <agents>/.env  (overrides)

Then applies provider aliases if LLM_* is missing or looks like a placeholder:
  GROQ_API_KEY        -> LLM_API_KEY + LLM_BASE_URL=https://api.groq.com/openai/v1
  OPENROUTER_API_KEY  -> LLM_API_KEY + LLM_BASE_URL=https://openrouter.ai/api/v1
  TOGETHER_API_KEY    -> LLM_API_KEY + LLM_BASE_URL=https://api.together.xyz/v1

Shell env vars always win.
"""
from __future__ import annotations

import os
from pathlib import Path

PROVIDER_ALIASES = [
    ("GROQ_API_KEY",       "https://api.groq.com/openai/v1",           "openai/gpt-oss-120b"),
    ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1",             "anthropic/claude-3.5-sonnet"),
    ("TOGETHER_API_KEY",   "https://api.together.xyz/v1",              "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    ("FIREWORKS_API_KEY",  "https://api.fireworks.ai/inference/v1",    "accounts/fireworks/models/llama-v3p3-70b-instruct"),
    ("DEEPINFRA_API_TOKEN","https://api.deepinfra.com/v1/openai",      "meta-llama/Meta-Llama-3.1-70B-Instruct"),
    ("HYPERBOLIC_API_KEY", "https://api.hyperbolic.xyz/v1",            "meta-llama/Meta-Llama-3.1-70B-Instruct"),
]


def _looks_like_placeholder(v: str) -> bool:
    v = (v or "").strip()
    if not v:
        return True
    if len(v) < 30:
        return True
    if v.lower() in {"sk-...", "sk-proj-...", "your-key-here", "changeme"}:
        return True
    return False


def _apply(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        # Empty values do NOT overwrite a previously-loaded value
        if val and key:
            os.environ[key] = val


def _apply_provider_aliases() -> None:
    current = os.getenv("LLM_API_KEY", "")
    if current and not _looks_like_placeholder(current):
        return  # user has a real key already
    for env_var, base_url, model in PROVIDER_ALIASES:
        candidate = os.getenv(env_var, "")
        if candidate and not _looks_like_placeholder(candidate):
            os.environ["LLM_API_KEY"] = candidate
            os.environ.setdefault("LLM_BASE_URL", base_url)
            os.environ.setdefault("LLM_MODEL", model)
            os.environ["_LLM_PROVIDER_SOURCE"] = env_var
            return


def load_env(env_path: str | Path = None) -> dict[str, str]:
    if env_path is not None:
        _apply(Path(env_path))
        _apply_provider_aliases()
        return dict(os.environ)

    here = Path(__file__).parent
    project_root = here.parent

    _apply(project_root / ".env")
    _apply(here / ".env")
    _apply_provider_aliases()
    return dict(os.environ)