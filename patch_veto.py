from pathlib import Path
import py_compile

ep = Path("harness_extensions.py")
lines = ep.read_text(encoding="utf-8").splitlines(keepends=True)

# Replace _test_launcher_vetoes with a bracket-counting version
new_vetoes = [
    'def _extract_list_body(src, name):\n',
    '    """Return the text between the [ and matching ] of `<name> = [...]`."""\n',
    '    marker = name + " = ["\n',
    '    idx = src.find(marker)\n',
    '    if idx < 0:\n',
    '        return None\n',
    '    start = idx + len(marker) - 1\n',
    '    depth = 0\n',
    '    i = start\n',
    '    while i < len(src):\n',
    '        c = src[i]\n',
    '        if c == "[":\n',
    '            depth += 1\n',
    '        elif c == "]":\n',
    '            depth -= 1\n',
    '            if depth == 0:\n',
    '                return src[start + 1:i]\n',
    '        i += 1\n',
    '    return None\n',
    '\n',
    '\n',
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
    '    print(f"[diag] vetoes: {len(patterns)} patterns loaded", flush=True)\n',
    '    for p in patterns:\n',
    '        print(f"[diag]   pattern: {p.pattern!r}", flush=True)\n',
    '    for q, should_veto in cases:\n',
    '        matched = [p.pattern for p in patterns if p.search(q.lower())]\n',
    '        got = bool(matched)\n',
    '        if got != should_veto:\n',
    '            misses.append((q, should_veto, got, matched))\n',
    '        print(f"[diag]   {q!r}: expected={should_veto} got={got}", flush=True)\n',
    '    if misses:\n',
    '        raise RuntimeError(f"{len(cases) - len(misses)}/{len(cases)} veto classifications")\n',
    '    return f"{len(cases)}/{len(cases)} veto classifications correct ({len(patterns)} patterns)"\n',
]

# Locate the current _test_launcher_vetoes (start) and next def (end)
start = None
for i, ln in enumerate(lines):
    if ln.startswith("def _test_launcher_vetoes("):
        start = i
        break
if start is None:
    raise SystemExit("[fail] _test_launcher_vetoes not found")
end = None
for j in range(start + 1, len(lines)):
    if lines[j].startswith("def ") or lines[j].startswith("# ---"):
        end = j
        break
if end is None:
    end = len(lines)

# Drop old definition, insert new one, keep a blank separator
tail = lines[end:]
while new_vetoes and new_vetoes[-1].strip() == "":
    new_vetoes.pop()
new_vetoes.append("\n")
lines = lines[:start] + new_vetoes + tail

ep.write_text("".join(lines), encoding="utf-8")

try:
    py_compile.compile(str(ep), doraise=True)
    print("[ok] replaced _test_launcher_vetoes with bracket-count version")
    print("[ok] harness_extensions.py compiles")
except py_compile.PyCompileError as e:
    print(f"[fail] {e}")
    raise SystemExit(1)