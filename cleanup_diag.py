from pathlib import Path
import py_compile

ep = Path("harness_extensions.py")
src = ep.read_text(encoding="utf-8")

# ---------- 1. Fix _test_critique_init to use a temp file ----------
old = (
    'def _test_critique_init():\n'
    '    from core.meta_cognition import SelfCritique\n'
    '    class StubLLM:\n'
    '        def generate(self, **kw): return None\n'
    '    sc = SelfCritique(StubLLM(), db_path=":memory:")\n'
    '    return f"patterns={len(sc.get_failure_patterns(min_count=1))} scores={sc.get_recent_scores(limit=5)}"'
)
new = (
    'def _test_critique_init():\n'
    '    import tempfile\n'
    '    from core.meta_cognition import SelfCritique\n'
    '    class StubLLM:\n'
    '        def generate(self, **kw): return None\n'
    '    tmp = tempfile.mkdtemp()\n'
    '    db_path = str(Path(tmp) / "critique_test.db")\n'
    '    sc = SelfCritique(StubLLM(), db_path=db_path)\n'
    '    p = len(sc.get_failure_patterns(min_count=1))\n'
    '    s = sc.get_recent_scores(limit=5)\n'
    '    return f"patterns={p} scores={s}"'
)
if old in src:
    src = src.replace(old, new, 1)
    print("[ok] fixed _test_critique_init (temp file instead of :memory:)")
else:
    print("[warn] critique_init body not matched — check manually")

# ---------- 2. Strip [diag] prints from _test_launcher_vetoes ----------
diag_lines = [
    '    print(f"[diag] vetoes: {len(patterns)} patterns loaded", flush=True)\n',
    '    for p in patterns:\n',
    '        print(f"[diag]   pattern: {p.pattern!r}", flush=True)\n',
    '        print(f"[diag]   {q!r}: expected={should_veto} got={got}", flush=True)\n',
]
# Simpler: rewrite the whole function body again, clean version.
clean_vetoes = [
    'def _test_launcher_vetoes():\n',
    '    src = (PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8")\n',
    '    body = _extract_list_body(src, "_COMPUTE_VETOES")\n',
    '    if body is None:\n',
    '        raise RuntimeError("_COMPUTE_VETOES not found")\n',
    '    patterns = [re.compile(p) for p in re.findall(r\'r"([^"]+)"\', body)]\n',
    '    cases = [\n',
    '        ("what is 5 + 3", True),\n',
    '        ("what is 15% of 240", True),\n',
    '        ("convert 100 usd to kes", True),\n',
    '        ("who is the president", False),\n',
    '        ("what is quantum entanglement", False),\n',
    '    ]\n',
    '    misses = []\n',
    '    for q, should_veto in cases:\n',
    '        got = any(p.search(q.lower()) for p in patterns)\n',
    '        if got != should_veto:\n',
    '            misses.append((q, should_veto, got))\n',
    '    if misses:\n',
    '        raise RuntimeError(f"{len(cases) - len(misses)}/{len(cases)} veto classifications; misses={misses}")\n',
    '    return f"{len(cases)}/{len(cases)} veto classifications correct ({len(patterns)} patterns)"\n',
]
# Find start of def and replace up to next def
lines = src.splitlines(keepends=True)
start = None
for i, ln in enumerate(lines):
    if ln.startswith("def _test_launcher_vetoes("):
        start = i
        break
if start is not None:
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("def ") or lines[j].startswith("# ---"):
            end = j
            break
    if end is None:
        end = len(lines)
    body = list(clean_vetoes)
    while body and body[-1].strip() == "":
        body.pop()
    body.append("\n")
    lines = lines[:start] + body + lines[end:]
    src = "".join(lines)
    print("[ok] cleaned _test_launcher_vetoes (removed [diag] prints)")
else:
    print("[warn] _test_launcher_vetoes not found")

# ---------- 3. Strip [diag] prints from _test_nosignup_explicit ----------
clean_explicit = [
    'def _test_nosignup_explicit():\n',
    '    from neo_nosignups import NeoToolPlugin\n',
    '    p = NeoToolPlugin(str(PROJECT_ROOT / "tools.json"))\n',
    '    cases = ["test regex", "edit pdf", "visualize json", "compress image"]\n',
    '    hits = sum(1 for q in cases if (p.handle_intent(q) or {}).get("has_tool"))\n',
    '    if hits < len(cases):\n',
    '        raise RuntimeError(f"only {hits}/{len(cases)} explicit intents fired")\n',
    '    return f"{hits}/{len(cases)} explicit intents fired"\n',
]
lines = src.splitlines(keepends=True)
start = None
for i, ln in enumerate(lines):
    if ln.startswith("def _test_nosignup_explicit("):
        start = i
        break
if start is not None:
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("def ") or lines[j].startswith("# ---"):
            end = j
            break
    if end is None:
        end = len(lines)
    body = list(clean_explicit)
    while body and body[-1].strip() == "":
        body.pop()
    body.append("\n")
    lines = lines[:start] + body + lines[end:]
    src = "".join(lines)
    print("[ok] cleaned _test_nosignup_explicit (removed [diag] prints)")
else:
    print("[warn] _test_nosignup_explicit not found")

ep.write_text(src, encoding="utf-8")
try:
    py_compile.compile(str(ep), doraise=True)
    print("[ok] harness_extensions.py compiles")
except py_compile.PyCompileError as e:
    print(f"[fail] {e}")
    raise SystemExit(1)