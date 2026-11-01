"""
neo_model_health.py — runtime known-good model discovery for hybrid_merger.

Drop this next to launcher.py. hybrid_merger.py imports it as `nmh`.

Role:
  - known_good_models.json  = pool of (provider, model) that returned 200
  - dead_models.json        = models that returned 404/410/decommissioned
  - throttled_models.json   = models that returned 429/401-ratelimit
"""

import json
import pathlib
import threading
import time

ROOT  = pathlib.Path(__file__).parent
STORE = ROOT / "known_good_models.json"
DEAD  = ROOT / "dead_models.json"
COOL  = ROOT / "throttled_models.json"

_LOCK = threading.Lock()

# Seed pool. Only entries confirmed alive on this key right now, plus a
# few fresh candidates the recorder will prune if they 404.
SEED_POOL = [
    # Groq — only ID confirmed live on this key
    ("groq",       "openai/gpt-oss-120b"),

    # OpenRouter — confirmed live in recent runs
    ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
    ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),

    # OpenRouter — fresh candidates. Recorder prunes any that 404.
    ("openrouter", "google/gemini-2.5-flash-preview:free"),
    ("openrouter", "google/gemini-2.0-flash-exp:free"),
    ("openrouter", "google/gemini-2.0-flash-thinking-exp:free"),
    ("openrouter", "deepseek/deepseek-r1:free"),

    # Local fallback (requires hybrid_merger v1.3+ with ollama in _PROVIDER_URL)
    ("ollama",     "qwen2.5:1.5b"),
]

COOLDOWN_SECONDS = 300


# ----------------------------------------------------------------- internals

def _load(path, default):
    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return default
        return json.loads(raw)
    except Exception:
        return default


def _save(path, data):
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True),
                       encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def _key(provider, model):
    return f"{provider}::{model}"


def _split_key(k):
    if "::" not in k:
        return None
    p, m = k.split("::", 1)
    return (p, m)


# ----------------------------------------------------------------- public API

def is_dead(provider, model):
    return _key(provider, model) in _load(DEAD, {})


def is_throttled(provider, model):
    t = _load(COOL, {}).get(_key(provider, model), 0)
    return (time.time() - t) < COOLDOWN_SECONDS


def record_success(provider, model):
    with _LOCK:
        good = _load(STORE, {})
        good[_key(provider, model)] = time.time()
        _save(STORE, good)

        cool = _load(COOL, {})
        if cool.pop(_key(provider, model), None) is not None:
            _save(COOL, cool)

        dead = _load(DEAD, {})
        if dead.pop(_key(provider, model), None) is not None:
            _save(DEAD, dead)


def record_dead(provider, model):
    with _LOCK:
        dead = _load(DEAD, {})
        dead[_key(provider, model)] = time.time()
        _save(DEAD, dead)

        good = _load(STORE, {})
        good.pop(_key(provider, model), None)
        _save(STORE, good)


def record_throttled(provider, model):
    with _LOCK:
        cool = _load(COOL, {})
        cool[_key(provider, model)] = time.time()
        _save(COOL, cool)


def known_good():
    good = _load(STORE, {})
    items = sorted(good.items(), key=lambda kv: -kv[1])
    out = []
    for k, _ in items:
        pm = _split_key(k)
        if pm:
            out.append(pm)
    return out


def get_pool(n, extra_candidates=None):
    """
    Return up to n diverse candidates as dicts:

        [{"provider": "groq", "id": "openai/gpt-oss-120b"}, ...]

    Order of preference:
      1. known_good_models.json  (recent successes)
      2. SEED_POOL               (known-live on our keys)
      3. extra_candidates        (caller-provided fallback)
    """
    seen, out = set(), []

    def try_add(p, m):
        k = _key(p, m)
        if k in seen:
            return
        if is_dead(p, m):
            return
        if is_throttled(p, m):
            return
        seen.add(k)
        out.append({"provider": p, "id": m})

    for p, m in known_good():
        try_add(p, m)
        if len(out) >= n:
            return out[:n]

    for p, m in SEED_POOL:
        try_add(p, m)
        if len(out) >= n:
            return out[:n]

    if extra_candidates:
        for cand in extra_candidates:
            if isinstance(cand, dict):
                p, m = cand.get("provider"), cand.get("id")
            else:
                try:
                    p, m = cand
                except Exception:
                    continue
            if p and m:
                try_add(p, m)
                if len(out) >= n:
                    return out[:n]

    return out[:n]


def stats():
    now = time.time()
    good = _load(STORE, {})
    dead = _load(DEAD, {})
    cool = _load(COOL, {})
    return {
        "known_good":       len(good),
        "dead":             len(dead),
        "throttled_total":  len(cool),
        "throttled_recent": sum(
            1 for t in cool.values() if (now - t) < COOLDOWN_SECONDS
        ),
        "cooldown_seconds": COOLDOWN_SECONDS,
    }


if __name__ == "__main__":
    print("neo_model_health — self-test")
    print()
    print("stats:", stats())
    print()
    print("seed pool preview (get_pool(5)):")
    for entry in get_pool(5):
        print(f"  {entry['provider']:10}  {entry['id']}")
    print()
    print("files in repo root:")
    for f in (STORE, DEAD, COOL):
        state = "exists" if f.exists() else "missing"
        print(f"  {f.name:28} {state}")