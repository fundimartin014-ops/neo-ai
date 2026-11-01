from pathlib import Path
import json, re, py_compile

root = Path(".").resolve()

# ============================================================
# 1. Fix niolesk URL in tools.json
# ============================================================
tj = root / "tools.json"
data = json.loads(tj.read_text(encoding="utf-8"))
fixed = 0
for t in data.get("tools", []):
    if t.get("id") == "niolesk":
        if not t["url"].startswith(("http://", "https://")):
            t["url"] = "https://" + t["url"]
            fixed += 1
tj.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[ok] tools.json: fixed {fixed} URL(s)")

# ============================================================
# 2. Make the live check more forgiving (browser UA, GET fallback)
# ============================================================
tp = root / "test_nosignup_tools.py"
src = tp.read_text(encoding="utf-8")

old_head = '''def head_ok(url: str, timeout: int = 5) -> Tuple[bool, str]:
    """HEAD request; if 405/501, fall back to a short GET."""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method,
                                         headers={"User-Agent": "Neo/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return True, str(r.status)
        except urllib.error.HTTPError as e:
            if e.code in (405, 501) and method == "HEAD":
                continue
            return True, f"{e.code}"      # server responded, just not 200
        except Exception as e:
            return False, f"{type(e).__name__}"
    return False, "unreachable"
'''
new_head = '''_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/125.0.0.0 Safari/537.36")


def head_ok(url: str, timeout: int = 10) -> Tuple[bool, str]:
    """Try HEAD then GET. Any HTTP response (even 4xx) counts as reachable;
    only network-level failures count as unreachable. Cloudflare-fronted
    sites often block HEAD, so the GET fallback matters.
    """
    last_err = "unreachable"
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url, method=method,
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return True, str(r.status)
        except urllib.error.HTTPError as e:
            # Any HTTP status means the host answered — treat as reachable.
            return True, f"{e.code}"
        except urllib.error.URLError as e:
            last_err = f"URLError:{getattr(e, 'reason', e)}"
        except Exception as e:
            last_err = f"{type(e).__name__}"
    return False, last_err
'''
if old_head in src:
    src = src.replace(old_head, new_head, 1)
    print("[ok] test_nosignup_tools.py: more forgiving reachability check")
else:
    print("[warn] head_ok body not matched")
tp.write_text(src, encoding="utf-8")

# ============================================================
# 3. Fix confidence() to catch hedging language
# ============================================================
vf = root / "core" / "reasoning" / "verification.py"
src = vf.read_text(encoding="utf-8")

# insert hedge patterns + helper after the MAX_STEPS line
hedge_anchor = "MAX_STEPS = 5\n"
hedge_block = '''MAX_STEPS = 5

# Phrases that signal the model itself was honest about limits. When any
# match, confidence is capped — otherwise the flags can all be True (the
# answer IS honest) while the underlying claim is still uncertain.
_HEDGE_PATTERNS = [
    r"\\bcannot\\s+(verify|confirm|be\\s+sure|say|answer|determine)",
    r"\\bcan'?t\\s+(verify|confirm|be\\s+sure|say|answer|determine)",
    r"\\bnot\\s+(sure|certain|verified|confirmed|able\\s+to\\s+verify)",
    r"\\bas\\s+far\\s+as\\s+.{0,30}(available|known|public|training|record)",
    r"\\b(may|might|could)\\s+have\\s+(changed|shifted|been)",
    r"\\buncertain\\b",
    r"\\bunverified\\b",
    r"\\bup\\s+to\\s+(20\\d\\d|my\\s+last)",
    r"\\bthe\\s+situation\\s+could\\s+have\\s+changed",
    r"\\bi\\s+(really\\s+)?don'?t\\s+know\\b",
    r"\\bi\\s+cannot\\s+(say|answer|determine)",
    r"\\bno\\s+current\\s+source",
]

def _hedge_cap(answer: str) -> Optional[float]:
    """Return a soft cap on confidence if the answer hedges, else None."""
    if not answer:
        return None
    t = answer.lower()
    # strongest: explicit "I don't know"
    if re.search(r"\\bi\\s+(really\\s+)?don'?t\\s+know\\b", t):
        return 0.45
    for pat in _HEDGE_PATTERNS:
        if re.search(pat, t):
            return 0.70
    return None
'''
if hedge_anchor in src and "_hedge_cap" not in src:
    src = src.replace(hedge_anchor, hedge_block, 1)
    print("[ok] verification.py: added hedge detection")
else:
    print("[warn] hedge anchor not found or already patched")

# replace confidence()
old_conf = '''    def confidence(self, crit: Dict[str, Any], n_problems: int) -> float:
        """0.0 to 1.0, from the boolean flags in the critique."""
        c = 0.0
        if crit.get("answers_question"): c += 0.30
        if crit.get("facts_grounded"):   c += 0.30
        if crit.get("is_complete"):      c += 0.20
        if crit.get("is_honest"):        c += 0.20
        # small penalty for unsolved problems
        c -= min(0.15, n_problems * 0.05)
        return round(max(0.0, min(1.0, c)), 3)
'''
new_conf = '''    def confidence(self, crit: Dict[str, Any], n_problems: int,
                   answer: str = "") -> float:
        """0.0 to 1.0, from the boolean flags + hedging language in the answer."""
        c = 0.0
        if crit.get("answers_question"): c += 0.30
        if crit.get("facts_grounded"):   c += 0.30
        if crit.get("is_complete"):      c += 0.20
        if crit.get("is_honest"):        c += 0.20
        # small penalty for unsolved problems
        c -= min(0.15, n_problems * 0.05)
        # hedge cap: if the answer itself admits limits, don't pretend 1.0
        cap = _hedge_cap(answer)
        if cap is not None:
            c = min(c, cap)
        return round(max(0.0, min(1.0, c)), 3)
'''
if old_conf in src:
    src = src.replace(old_conf, new_conf, 1)
    print("[ok] verification.py: confidence() now takes answer + hedge cap")
else:
    print("[warn] confidence() body not matched")

# update the call site
old_call = '        conf = self.confidence(crit, len(crit.get("problems", [])))'
new_call = '        conf = self.confidence(crit, len(crit.get("problems", [])), answer=d)'
if old_call in src:
    src = src.replace(old_call, new_call, 1)
    print("[ok] verification.py: call site updated")
else:
    print("[warn] confidence call site not found")

vf.write_text(src, encoding="utf-8")

# ============================================================
# 4. compile
# ============================================================
for p in (root / "test_nosignup_tools.py",
          root / "core" / "reasoning" / "verification.py"):
    try:
        py_compile.compile(str(p), doraise=True)
        print(f"[ok] {p.relative_to(root)} compiles")
    except py_compile.PyCompileError as e:
        print(f"[fail] {p.relative_to(root)}: {e}")
        raise SystemExit(1)

print()
print("=" * 72)
print("  DONE")
print("=" * 72)
print()
print("Retest:")
print("  python test_nosignup_tools.py --all          # niolesk should now pass")
print("  python test_nosignup_tools.py --live         # fewer false negatives")
print()
print("  python -c \"from core.local_llm import LocalLLM; \\")
print("    from core.reasoning.verification import VerificationLayer; \\")
print("    import json; out = VerificationLayer(LocalLLM()).reason(\\")
print("      'What is the capital of Burkina Faso and who leads it?'); \\")
print("    print('confidence:', out['confidence']); print('answer:', out['answer'][:200])\"")
print()
print("The Burkina Faso answer should now show confidence ~0.7 (hedged),")
print("not 1.0 — because the model itself admitted it cannot verify.")