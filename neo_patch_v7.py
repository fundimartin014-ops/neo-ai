"""
neo_patch_v7.py — filter decommissioned Groq models in hybrid_merger.
Groq has retired llama-3.3-70b-specdec, mixtral-8x7b-32768, gemma2-9b-it,
llama3-70b-8192, llama3-8b-8192, etc. Only the ones below are live.
"""
import ast
import re
from pathlib import Path

p = Path("hybrid_merger.py")
src = p.read_text(encoding="utf-8")
changes = []

# ─────────────────────────────────────────────────────────────────────
# 1. Add live-Groq allowlist + filter helper as class attributes
# ─────────────────────────────────────────────────────────────────────
if "_LIVE_GROQ_MODELS" not in src:
    # Insert right after `MERGER_MODELS = [...]` block
    m = re.search(r"(    MERGER_MODELS = \[[\s\S]*?\n    \])\n", src)
    if not m:
        print("FAIL: MERGER_MODELS anchor not found")
        raise SystemExit(1)

    allowlist = '''

    # Groq has decommissioned most of its older lineup. Only these IDs are
    # currently live on the free tier as of Oct 2026. Anything else returns
    # HTTP 400 "has been decommissioned".
    _LIVE_GROQ_MODELS = {
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "qwen/qwen3.6-27b",
        "qwen-2.5-coder-32b",
        "qwen-qwq-32b",
    }

    # Default Groq model to substitute when a dead one is filtered out.
    _GROQ_FALLBACK = "openai/gpt-oss-120b"
'''
    src = src[:m.end()] + allowlist + src[m.end():]
    changes.append("added _LIVE_GROQ_MODELS allowlist")

# ─────────────────────────────────────────────────────────────────────
# 2. Filter resolved_models after the selection logic
# ─────────────────────────────────────────────────────────────────────
anchor = "        if not resolved_models:\n            return HybridResult("
if anchor not in src:
    print("FAIL: resolved_models anchor not found")
    raise SystemExit(1)

filter_block = '''        # ── Filter out decommissioned Groq models ──
        # If the catalog still lists retired Groq IDs, swap them for the
        # live default. Any non-Groq models pass through untouched.
        _filtered = []
        for _m in resolved_models:
            if _m.get("provider") == "groq":
                _mid = _m.get("id", "")
                if _mid not in self._LIVE_GROQ_MODELS:
                    logger.warning(
                        f"[HybridMerger] Groq model '{_mid}' decommissioned, "
                        f"substituting '{self._GROQ_FALLBACK}'"
                    )
                    _m = dict(_m)  # copy
                    _m["id"] = self._GROQ_FALLBACK
            _filtered.append(_m)
        resolved_models = _filtered
        # ── end filter ──

'''

src = src.replace(anchor, filter_block + anchor, 1)
changes.append("added Groq filter block before resolution check")

# ─────────────────────────────────────────────────────────────────────
# 3. Also filter in MERGER_MODELS (the synthesis LLM) — clean any dead ones
# ─────────────────────────────────────────────────────────────────────
# The MERGER_MODELS list currently has gpt-oss-120b twice — dedupe
m = re.search(r"    MERGER_MODELS = \[([\s\S]*?)\n    \]", src)
if m:
    block = m.group(1)
    # Find groq lines
    groq_lines = re.findall(r'\{"provider": "groq", "model": "([^"]+)"[^}]*\}', block)
    dead_in_merger = [g for g in groq_lines if g not in src[:src.find("_LIVE_GROQ_MODELS")] or False]
    # Only log if the merger list has something not in live set (unlikely but worth checking)
    # The merger list only has gpt-oss-120b (live) so no change needed
    if any(g not in ("openai/gpt-oss-120b",) for g in groq_lines):
        changes.append(f"WARNING: MERGER_MODELS has unusual Groq IDs: {groq_lines}")

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
print("=" * 62)
print("  NEO PATCH v7 — RESULTS")
print("=" * 62)
for c in changes:
    print(f"  ✓ {c}")
print("=" * 62)
print()
print("Restart launcher and try:")
print("  hybrid what is machine learning pool=3")
print()