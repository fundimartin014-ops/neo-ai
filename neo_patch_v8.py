"""
neo_patch_v8.py — enrich hybrid pool with live Groq + OpenRouter models.

A. Expands _LIVE_GROQ_MODELS to include all currently-serving Groq IDs.
B. Adds a curated fallback pool with mixed Groq + OpenRouter free models.
   Whenever catalog resolution yields < 2 unique (provider, id) pairs,
   we swap to the curated pool so hybrid actually runs diverse models.
"""
import ast
import re
from pathlib import Path

p = Path("hybrid_merger.py")
src = p.read_text(encoding="utf-8")
changes = []


# ─────────────────────────────────────────────────────────────────────
# 1. Replace _LIVE_GROQ_MODELS with a bigger, accurate set
# ─────────────────────────────────────────────────────────────────────
new_live_groq = '''    _LIVE_GROQ_MODELS = {
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "qwen/qwen3.6-27b",
        "qwen-2.5-coder-32b",
        "qwen-qwq-32b",
        "deepseek-r1-distill-llama-70b",
        "deepseek-r1-distill-qwen-32b",
        "gemma-7b-it",
    }'''

m = re.search(r"    _LIVE_GROQ_MODELS = \{[\s\S]*?\n    \}", src)
if m:
    src = src[:m.start()] + new_live_groq + src[m.end():]
    changes.append("expanded _LIVE_GROQ_MODELS to 10 entries")
else:
    # Fallback: insert just before _GROQ_FALLBACK if that exists
    anchor = "    _GROQ_FALLBACK = "
    if anchor in src:
        idx = src.find(anchor)
        src = src[:idx] + new_live_groq + "\n\n" + src[idx:]
        changes.append("inserted _LIVE_GROQ_MODELS")
    else:
        print("FAIL: cannot locate _LIVE_GROQ_MODELS anchor")
        raise SystemExit(1)


# ─────────────────────────────────────────────────────────────────────
# 2. Add _LIVE_OPENROUTER_MODELS + _CURATED_POOL (only once)
# ─────────────────────────────────────────────────────────────────────
if "_CURATED_POOL" not in src:
    m = re.search(r"(    _LIVE_GROQ_MODELS = \{[\s\S]*?\n    \})", src)
    insert_after = m.end()

    pool_block = '''


    # Current live OpenRouter free-tier models. IDs rotate monthly — verify
    # against https://openrouter.ai/api/v1/models if any of these 404.
    _LIVE_OPENROUTER_MODELS = {
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "qwen/qwen3.8-27b:free",
        "cohere/north-mini-code:free",
        "liquid/lfm-2.5-2.6b:free",
    }

    # Curated fallback pool. Used whenever catalog resolution yields fewer
    # than 2 distinct (provider, id) pairs — which happens when the catalog
    # is stale and all entries collapse to the same Groq fallback. Guarantees
    # hybrid runs across several live models from multiple providers.
    _CURATED_POOL = [
        {"provider": "groq",       "id": "openai/gpt-oss-120b",
         "base_url": "https://api.groq.com/openai/v1",  "env": "GROQ_API_KEY"},
        {"provider": "openrouter", "id": "google/gemma-4-31b-it:free",
         "base_url": "https://openrouter.ai/api/v1",    "env": "OPENROUTER_API_KEY"},
        {"provider": "groq",       "id": "llama-3.1-8b-instant",
         "base_url": "https://api.groq.com/openai/v1",  "env": "GROQ_API_KEY"},
        {"provider": "openrouter", "id": "nvidia/nemotron-3-super-120b-a12b:free",
         "base_url": "https://openrouter.ai/api/v1",    "env": "OPENROUTER_API_KEY"},
        {"provider": "groq",       "id": "qwen/qwen3.6-27b",
         "base_url": "https://api.groq.com/openai/v1",  "env": "GROQ_API_KEY"},
        {"provider": "openrouter", "id": "qwen/qwen3.8-27b:free",
         "base_url": "https://openrouter.ai/api/v1",    "env": "OPENROUTER_API_KEY"},
        {"provider": "groq",       "id": "llama-3.3-70b-versatile",
         "base_url": "https://api.groq.com/openai/v1",  "env": "GROQ_API_KEY"},
        {"provider": "openrouter", "id": "cohere/north-mini-code:free",
         "base_url": "https://openrouter.ai/api/v1",    "env": "OPENROUTER_API_KEY"},
    ]
'''
    src = src[:insert_after] + pool_block + src[insert_after:]
    changes.append("added _LIVE_OPENROUTER_MODELS + _CURATED_POOL (8 mixed models)")
else:
    changes.append("skip (_CURATED_POOL already present)")


# ─────────────────────────────────────────────────────────────────────
# 3. Diversity check — swap to curated pool if catalog was duplicate-heavy
# ─────────────────────────────────────────────────────────────────────
anchor = "        resolved_models = _filtered\n"
if anchor not in src:
    print("FAIL: v7 filter anchor not found — apply v7 patch first")
    raise SystemExit(1)

if "Diversity check" not in src:
    dup_check = '''
        # ── Diversity check ──
        # If the catalog collapsed to fewer than 2 unique (provider, id)
        # pairs (which happens when it's stale and every Groq entry hits
        # the _GROQ_FALLBACK swap), replace with the curated pool so the
        # hybrid actually runs across multiple live models from multiple
        # providers. Only applies when caller used auto_pool — explicit
        # model_pool choices are respected untouched.
        if not model_pool:
            _unique = {(mm.get("provider"), mm.get("id")) for mm in resolved_models}
            if len(_unique) < 2:
                logger.warning(
                    f"[HybridMerger] Catalog gave {len(_unique)} unique model(s), "
                    f"swapping to curated pool for real diversity"
                )
                resolved_models = list(self._CURATED_POOL)[:max(pool_size, 2)]
                _unique = {(mm.get("provider"), mm.get("id")) for mm in resolved_models}
                logger.info(
                    f"[HybridMerger] Curated pool selected: {sorted(_unique)}"
                )
        # ── end diversity check ──
'''
    src = src.replace(anchor, anchor + dup_check, 1)
    changes.append("added diversity check + curated pool fallback")
else:
    changes.append("skip (diversity check already present)")


# ─────────────────────────────────────────────────────────────────────
# Validate + write
# ─────────────────────────────────────────────────────────────────────
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"FAIL syntax: {e}")
    raise SystemExit(1)

p.write_text(src, encoding="utf-8")

print()
print("=" * 68)
print("  NEO PATCH v8 — RESULTS")
print("=" * 68)
for c in changes:
    print(f"  ✓ {c}")
print("=" * 68)
print()
print("Reboot: python launcher.py")
print("Test:   hybrid what is machine learning pool=5")
print()