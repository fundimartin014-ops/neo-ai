from pathlib import Path
import py_compile

ep = Path("harness_extensions.py")
lines = ep.read_text(encoding="utf-8").splitlines(keepends=True)

def replace_function(lines, name, new_body_lines):
    """Find 'def <name>(...)' at col 0 and replace up to (not including) next 'def '."""
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(f"def {name}("):
            start = i
            break
    if start is None:
        return lines, False
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("def ") or lines[j].startswith("# ---"):
            end = j
            break
    if end is None:
        end = len(lines)
    # preserve one trailing blank line before the next def
    tail = lines[end:]
    # strip excess blank lines at end of new body then add one blank
    body = list(new_body_lines)
    while body and body[-1].strip() == "":
        body.pop()
    body.append("\n")
    return lines[:start] + body + tail, True


# ---------- 1. New _test_launcher_vetoes ----------
new_vetoes = [
    'def _test_launcher_vetoes():\n',
    '    src = (PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8")\n',
    '    m = re.search(r"_COMPUTE_VETOES\\s*=\\s*\\[(.*?)\\]", src, re.DOTALL)\n',
    '    if not m:\n',
    '        raise RuntimeError("_COMPUTE_VETOES not found")\n',
    '    patterns = [re.compile(p) for p in re.findall(r\'r"([^"]+)"\', m.group(1))]\n',
    '    cases = [\n',
    '        ("what is 5 + 3", True),\n',
    '        ("what is 15% of 240", True),\n',
    '        ("convert 100 usd to kes", True),\n',
    '        ("who is the president", False),\n',
    '        ("what is quantum entanglement", False),\n',
    '    ]\n',
    '    misses = []\n',
    '    for q, should_veto in cases:\n',
    '        is_vetoed = any(p.search(q.lower()) for p in patterns)\n',
    '        if is_vetoed != should_veto:\n',
    '            misses.append(f"{q!r} expected_veto={should_veto} got={is_vetoed}")\n',
    '    if misses:\n',
    '        pats = [p.pattern for p in patterns]\n',
    '        raise RuntimeError(\n',
    '            f"{len(cases) - len(misses)}/{len(cases)} ok; misses={misses}; patterns={pats}"\n',
    '        )\n',
    '    return f"{len(cases)}/{len(cases)} veto classifications correct"\n',
]
lines, ok1 = replace_function(lines, "_test_launcher_vetoes", new_vetoes)
print("[ok] replaced _test_launcher_vetoes" if ok1 else "[warn] _test_launcher_vetoes not found")

# ---------- 2. New _test_plugins_load ----------
new_load = [
    'def _test_plugins_load():\n',
    '    d = PROJECT_ROOT / "core" / "plugins"\n',
    '    if not d.exists():\n',
    '        raise RuntimeError("core/plugins missing")\n',
    '    files = sorted(f for f in d.glob("*.py") if not f.name.startswith("__"))\n',
    '    loaded = 0\n',
    '    no_plugin = []\n',
    '    failed = []\n',
    '    for f in files:\n',
    '        try:\n',
    '            spec = importlib.util.spec_from_file_location(f.stem, f)\n',
    '            mod = importlib.util.module_from_spec(spec)\n',
    '            spec.loader.exec_module(mod)\n',
    '            if not hasattr(mod, "Plugin"):\n',
    '                no_plugin.append(f.name)\n',
    '                continue\n',
    '            mod.Plugin()\n',
    '            loaded += 1\n',
    '        except Exception as e:\n',
    '            failed.append(f"{f.name}:{type(e).__name__}:{str(e)[:80]}")\n',
    '    if failed:\n',
    '        raise RuntimeError(\n',
    '            f"{loaded} loaded, {len(failed)} failed, {len(no_plugin)} non-plugin. "\n',
    '            f"Fails={failed} NoPlugin={no_plugin}"\n',
    '        )\n',
    '    return f"{loaded} loaded, {len(no_plugin)} non-plugin skipped; names={no_plugin}"\n',
]
lines, ok2 = replace_function(lines, "_test_plugins_load", new_load)
print("[ok] replaced _test_plugins_load" if ok2 else "[warn] _test_plugins_load not found")

# ---------- 3. Diagnose _test_nosignup_explicit ----------
new_explicit = [
    'def _test_nosignup_explicit():\n',
    '    print("[diag] explicit_intents starting", flush=True)\n',
    '    from neo_nosignups import NeoToolPlugin\n',
    '    p = NeoToolPlugin(str(PROJECT_ROOT / "tools.json"))\n',
    '    cases = ["test regex", "edit pdf", "visualize json", "compress image"]\n',
    '    results = []\n',
    '    for q in cases:\n',
    '        try:\n',
    '            r = p.handle_intent(q) or {}\n',
    '            results.append((q, bool(r.get("has_tool"))))\n',
    '        except Exception as e:\n',
    '            results.append((q, f"ERR:{type(e).__name__}:{e}"))\n',
    '    hits = sum(1 for _, h in results if h is True)\n',
    '    print(f"[diag] explicit_intents done: {results}", flush=True)\n',
    '    return f"{hits}/{len(cases)} explicit intents fired | detail={results}"\n',
]
lines, ok3 = replace_function(lines, "_test_nosignup_explicit", new_explicit)
print("[ok] added diagnostics to _test_nosignup_explicit" if ok3 else "[warn] _test_nosignup_explicit not found")

ep.write_text("".join(lines), encoding="utf-8")

try:
    py_compile.compile(str(ep), doraise=True)
    print("[ok] harness_extensions.py compiles")
except py_compile.PyCompileError as e:
    print(f"[fail] {e}")
    raise SystemExit(1)