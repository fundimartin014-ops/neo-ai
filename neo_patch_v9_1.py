"""
neo_patch_v9_1.py

Fixes the substitution collapse and wires the pool to neo_model_health.

Patches hybrid_merger.py:
  [1] Replace _LIVE_GROQ_MODELS with confirmed-live list.
  [2] Drop dead Groq models instead of substituting (was collapsing pool).
  [3] Pad resolved_models to pool_size from nmh.get_pool().
  [4] Record success/dead/throttled outcomes so pool self-heals.

Prereq: neo_model_health.get_pool() must return dicts, not tuples.
        (See v9.1 step 1 in the chat — one-line edit.)

Run:   python neo_patch_v9_1.py --dry-run
       python neo_patch_v9_1.py
"""

import argparse
import pathlib
import re
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).parent.resolve()
STAMP = time.strftime("%Y%m%d-%H%M%S")
DRY = False

# ----------------------------------------------------------------- anchors

NEW_LIVE_GROQ = '''_LIVE_GROQ_MODELS = [
    # Confirmed-live on our key. Anything else that 404s at call time
    # is pruned by neo_model_health.record_dead() and won't be retried.
    "openai/gpt-oss-120b",
    "openai/gpt-oss-1b",
    "qwen-qwq-32b",
    "deepseek-r1-distill-llama-70b",
    "deepseek-r1-distill-qwen-32b",
    "qwen-2.5-coder-32b",
]'''

NEW_FILTER = '''        _filtered = []
        for _m in resolved_models:
            if _m.get("provider") == "groq":
                _mid = _m.get("id", "")
                if _mid not in self._LIVE_GROQ_MODELS:
                    logger.info(
                        f"[HybridMerger] Dropping dead Groq model '{_mid}'"
                    )
                    try:
                        nmh.record_dead("groq", _mid)
                    except Exception:
                        pass
                    continue
            _filtered.append(_m)
        resolved_models = _filtered
'''

PADDING = '''
        # ── neo_patch_v9_1: pad to pool_size from known-good pool ──
        if not model_pool and len(resolved_models) < pool_size:
            _have = {(m.get("provider"), m.get("id")) for m in resolved_models}
            try:
                _pad = nmh.get_pool(pool_size)
            except Exception:
                _pad = []
            for _cand in _pad:
                _ck = (_cand.get("provider"), _cand.get("id"))
                if _ck in _have:
                    continue
                resolved_models.append(_cand)
                _have.add(_ck)
                if len(resolved_models) >= pool_size:
                    break
        # ── end padding ──
'''

RECORDER = '''        outputs = await asyncio.gather(*tasks, return_exceptions=True)

        # ── neo_patch_v9_1: record outcomes for pool self-heal ──
        for _m, _out in zip(resolved_models, outputs):
            _prov = _m.get("provider", "?")
            _mid  = _m.get("id", "?")
            try:
                if isinstance(_out, Exception):
                    _err = str(_out)
                    if "429" in _err or "rate" in _err.lower():
                        nmh.record_throttled(_prov, _mid)
                    elif ("404" in _err or "not_found" in _err
                          or "does not exist" in _err.lower()):
                        nmh.record_dead(_prov, _mid)
                else:
                    nmh.record_success(_prov, _mid)
            except Exception:
                pass
        # ── end outcome recording ──
'''

GATHER_ANCHOR = "outputs = await asyncio.gather(*tasks, return_exceptions=True)"
DIVERSITY_END = "# ── end diversity check ──"

# ----------------------------------------------------------------- helpers


def backup(path):
    b = path.with_name(path.name + f".bak.{STAMP}")
    shutil.copy2(path, b)
    return b


def write(path, text):
    if DRY:
        print(f"    (dry-run) would write {path.name}")
        return
    backup(path)
    path.write_text(text, encoding="utf-8")


def find(name):
    p = ROOT / name
    if p.exists():
        return p
    hits = list(ROOT.rglob(name))
    return hits[0] if hits else None


# ----------------------------------------------------------------- patches


def patch_live_groq():
    print("[1] _LIVE_GROQ_MODELS in hybrid_merger.py")
    f = find("hybrid_merger.py")
    if not f:
        print("    ✗ hybrid_merger.py not found")
        return False
    text = f.read_text(encoding="utf-8")
    pat = re.compile(r"_LIVE_GROQ_MODELS\s*=\s*\[.*?\]", re.DOTALL)
    new, n = pat.subn(NEW_LIVE_GROQ, text, count=1)
    if n != 1:
        print("    ✗ no _LIVE_GROQ_MODELS assignment found")
        return False
    write(f, new)
    print("    ✓ rewritten (6 confirmed-live entries)")
    return True


def patch_filter():
    print("[2] drop dead models instead of substituting")
    f = find("hybrid_merger.py")
    if not f:
        return False
    text = f.read_text(encoding="utf-8")

    # Match the entire filter block from "_filtered = []" through
    # "resolved_models = _filtered".
    pat = re.compile(
        r"(?P<indent>[ \t]*)_filtered = \[\]\n"
        r".*?resolved_models = _filtered\n",
        re.DOTALL,
    )
    m = pat.search(text)
    if not m:
        print("    ✗ filter block not found")
        return False

    new = text[:m.start()] + NEW_FILTER + text[m.end():]
    write(f, new)
    print("    ✓ substitution replaced with skip + record_dead")
    return True


def patch_padding():
    print("[3] pad pool from known-good store")
    f = find("hybrid_merger.py")
    if not f:
        return False
    text = f.read_text(encoding="utf-8")
    if "neo_patch_v9_1: pad to pool_size" in text:
        print("    ✓ already applied")
        return True
    if DIVERSITY_END not in text:
        print(f"    ✗ anchor '{DIVERSITY_END}' not found")
        return False
    new = text.replace(DIVERSITY_END, DIVERSITY_END + PADDING, 1)
    write(f, new)
    print("    ✓ padding step inserted")
    return True


def patch_recorder():
    print("[4] instrument success/failure recording")
    f = find("hybrid_merger.py")
    if not f:
        return False
    text = f.read_text(encoding="utf-8")
    if "neo_patch_v9_1: record outcomes" in text:
        print("    ✓ already applied")
        return True
    if GATHER_ANCHOR not in text:
        print("    ✗ asyncio.gather anchor not found")
        return False
    new = text.replace(GATHER_ANCHOR, RECORDER.rstrip(), 1)
    write(f, new)
    print("    ✓ recorder wired into gather step")
    return True


# ----------------------------------------------------------------- main


def main():
    global DRY
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    DRY = args.dry_run

    print("=" * 68)
    print("  NEO PATCH v9.1 — drop dead, pad from known-good, self-heal")
    print("=" * 68)
    if DRY:
        print("  (dry run — nothing will be written)")
    print()

    # Sanity: neo_model_health must exist and get_pool must return dicts.
    nmh_path = find("neo_model_health.py")
    if not nmh_path:
        print("  ✗ neo_model_health.py not found in repo root.")
        print("    Drop it next to launcher.py and re-run.")
        return 1
    nmh_text = nmh_path.read_text(encoding="utf-8")
    if 'out.append((p, m))' in nmh_text:
        print("  ✗ neo_model_health.py still returns tuples.")
        print("    Fix this line inside get_pool():")
        print("        out.append((p, m))")
        print("    →   out.append({\"provider\": p, \"id\": m})")
        return 1
    if '"provider": p, "id": m' not in nmh_text and "'provider': p" not in nmh_text:
        print("  ⚠ could not confirm get_pool returns dicts; proceeding anyway.")

    results = []
    results.append(("live groq list", patch_live_groq()))
    results.append(("filter (skip dead)", patch_filter()))
    results.append(("padding step", patch_padding()))
    results.append(("outcome recorder", patch_recorder()))

    print()
    print("=" * 68)
    print("  SUMMARY")
    print("=" * 68)
    for name, ok in results:
        print(f"  {'✓' if ok else '✗'} {name}")

    print()
    if all(ok for _, ok in results):
        print("Next:")
        print("  1. python launcher.py")
        print("  2. hybrid what is machine learning pool=5")
        print("  3. hybrid what is machine learning pool=5  (again)")
        print()
        print("First run should drop 4 dead Groq models, keep the live ones,")
        print("pad from the pool, and record outcomes. Second run should")
        print("already be near 5/5 because known_good_models.json now has")
        print("entries.")
    else:
        print("Some patches failed — paste back the ✗ sections and")
        print("I'll target them exactly.")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())