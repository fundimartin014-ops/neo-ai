from pathlib import Path
import py_compile

vf = Path("core/reasoning/verification.py")
src = vf.read_text(encoding="utf-8")

# ---------- 1. Verify the call site was patched ----------
has_call = "answer=d" in src
has_hedge_fn = "_hedge_cap" in src
print(f"[check] _hedge_cap present: {has_hedge_fn}")
print(f"[check] call site uses answer=d: {has_call}")

if not has_hedge_fn:
    print("[fail] hedge function missing — re-run fix_confidence.py first")
    raise SystemExit(1)

# ---------- 2. Broaden the hedge patterns ----------
# Find the existing _HEDGE_PATTERNS block and replace it with a wider list.
import re
m = re.search(
    r"_HEDGE_PATTERNS\s*=\s*\[(.*?)\]\s*\n",
    src, re.DOTALL,
)
if not m:
    print("[fail] _HEDGE_PATTERNS block not found")
    raise SystemExit(1)

new_patterns = r'''_HEDGE_PATTERNS = [
    # explicit "can't verify / don't know"
    r"\bcannot\s+(verify|confirm|be\s+sure|say|answer|determine)",
    r"\bcan'?t\s+(verify|confirm|be\s+sure|say|answer|determine)",
    r"\bi\s+(really\s+)?do(?:n'?t|\s+not)\s+know\b",
    r"\bi\s+cannot\s+(say|answer|determine)",
    # lack-of-information phrasings (this was the miss)
    r"\b(?:do|does)\s+not\s+have\s+(?:that|this|any)\s+information\b",
    r"\b(?:do|does)n'?t\s+have\s+(?:that|this|any)\s+information\b",
    r"\bi\s+(?:do\s+not|don'?t)\s+have\s+(?:that|this|any|access\s+to)",
    r"\bnot\s+(?:sure|certain|verified|confirmed|able\s+to\s+verify)",
    r"\bno\s+(?:current|up-to-date|reliable)\s+(?:source|information|data)",
    r"\bmy\s+information\s+may\s+be\s+(?:out\s+of\s+date|stale|incomplete)",
    # timestamped knowledge
    r"\bas\s+of\s+(?:the\s+)?(?:most\s+)?(?:recent|latest|current|my\s+last)",
    r"\bas\s+far\s+as\s+.{0,40}(available|known|public|training|record|aware)",
    r"\bup\s+to\s+(?:20\d\d|my\s+last)",
    r"\b(?:knowledge|training)\s+(?:cutoff|data)",
    r"\bsince\s+(?:my|the)\s+last",
    # conditionals on change
    r"\bif\s+(?:there\s+have\s+been|things\s+have|anything\s+has)\s+(?:changed|shifted)",
    r"\b(?:may|might|could)\s+have\s+(?:changed|shifted|been)",
    r"\bthe\s+situation\s+(?:could|may|might)\s+have\s+changed",
    r"\bafter\s+this\s+date",
    # generic uncertainty words
    r"\buncertain\b",
    r"\bunverified\b",
    r"\bnot\s+up\s+to\s+date\b",
]'''

src = src[:m.start()] + new_patterns + "\n" + src[m.end():]
print("[ok] replaced _HEDGE_PATTERNS with broader set")

# ---------- 3. Add a diagnostic print inside reason() ----------
# If _hedge_cap returns a value, print it so we can see it fire.
old_conf_call = "        conf = self.confidence(crit, len(crit.get(\"problems\", [])), answer=d)"
new_conf_call = (
    "        conf = self.confidence(crit, len(crit.get(\"problems\", [])), answer=d)\n"
    "        if self.verbose:\n"
    "            _cap = _hedge_cap(d)\n"
    "            print(f\"[verification] hedge_cap={_cap} final_conf={conf}\")\n"
    "            if _cap is not None:\n"
    "                import re as _re\n"
    "                _t = d.lower()\n"
    "                for _p in _HEDGE_PATTERNS:\n"
    "                    if _re.search(_p, _t):\n"
    "                        print(f\"[verification]   matched: {_p}\")\n"
    "                        break"
)
if old_conf_call in src:
    src = src.replace(old_conf_call, new_conf_call, 1)
    print("[ok] added verbose diagnostic in reason()")
elif "hedge_cap={_cap}" in src:
    print("[skip] diagnostic already present")
else:
    print("[warn] reason() call site not found — diagnostic not added")
    print("       grep output for call site:")
    for i, ln in enumerate(src.splitlines(), 1):
        if "conf = self.confidence" in ln:
            print(f"       line {i}: {ln.strip()}")

vf.write_text(src, encoding="utf-8")

try:
    py_compile.compile(str(vf), doraise=True)
    print("[ok] verification.py compiles")
except py_compile.PyCompileError as e:
    print(f"[fail] {e}")
    raise SystemExit(1)