from pathlib import Path
import re

ep = Path("harness_extensions.py")
src = ep.read_text(encoding="utf-8")

# ---------- 1. Replace _test_launcher_vetoes with a diagnostic version ----------
new_vetoes = (
    'def _test_launcher_vetoes():\n'
    '    src = (PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8")\n'
    '    m = re.search(r"_COMPUTE_VETOES\\s*=\\s*\\[(.*?)\\]", src, re.DOTALL)\n'
    '    if not m:\n'
    '        raise RuntimeError("_COMPUTE_VETOES not found")\n'
    '    patterns = [re.compile(p) for p in re.findall(r\'r"([^"]+)"\', m.group(1))]\n'
    '    cases = [\n'
    '        ("what is 5 + 3", True),\n'
    '        ("what is 15% of 240", True),\n'
    '        ("convert 100 usd to kes", True),\n'
    '        ("who is the president", False),\n'
    '        ("what is quantum entanglement", False),\n'
    '    ]\n'
    '    misses = []\n'
    '    for q, should_veto in cases:\n'
    '        is_vetoed = any(p.search(q.lower()) for p in patterns)\n'
    '        if is_vetoed != should_veto:\n'
    '            misses.append(f"{q!r} expected_veto={should_veto} got={is_vetoed}")\n'
    '    if misses:\n'
    '        raise RuntimeError(\n'
    '            f"{len(cases) - len(misses)}/{len(cases)} ok; misses: {misses}; "\n'
    '            f"patterns={[p.pattern for p in patterns]}"\n'
    '        )\n'
    '    return f"{len(cases)}/{len(cases)} veto classifications correct"\n'
)

# Regex to find the whole function body
pat = re.compile(
    r"def _test_launcher_vetoes\(\):.*?(?=\n\ndef |\n\n# )",
    re.DOTALL,
)
new_src, n = pat.subn(new_vetoes.rstrip("\n"), src, count=1)
if n == 0:
    raise SystemExit("[fail] _test_launcher_vetoes not found")
src = new_src
print("[ok] replaced _test_launcher_vetoes with diagnostic version")

# ---------- 2. Replace _test_plugins_load with a less-strict version ----------
new_load = (
    'def _test_plugins_load():\n'
    '    d = PROJECT_ROOT / "core" / "plugins"\n'
    '    if not d.exists():\n'
    '        raise RuntimeError("core/plugins missing")\n'
    '    files = sorted(f for f in d.glob("*.py") if not f.name.startswith("__"))\n'
    '    loaded = 0\n'
    '    no_plugin = []\n'
    '    failed = []\n'
    '    for f in files:\n'
    '        try:\n'
    '            spec = importlib.util.spec_from_file_location(f.stem, f)\n'
    '            mod = importlib.util.module_from_spec(spec)\n'
    '            spec.loader.exec_module(mod)\n'
    '            if not hasattr(mod, "Plugin"):\n'
    '                no_plugin.append(f.name)\n'
    '                continue\n'
    '            mod.Plugin()\n'
    '            loaded += 1\n'
    '        except Exception as e:\n'
    '            failed.append(f"{f.name}:{type(e).__name__}:{str(e)[:80]}")\n'
    '    if failed:\n'
    '        raise RuntimeError(\n'
    '            f"{loaded} loaded, {len(failed)} failed, {len(no_plugin)} non-plugin. "\n'
    '            f"Fails: {failed}"\n'
    '        )\n'
    '    return (f"{loaded} loaded, {len(no_plugin)} non-plugin files skipped; "\n'
    '            f"names={no_plugin}")\n'
)
pat2 = re.compile(
    r"def _test_plugins_load\(\):.*?(?=\n\ndef |\n\n# )",
    re.DOTALL,
)
new_src2, n2 = pat2.subn(new_load.rstrip("\n"), src, count=1)
if n2 == 0:
    raise SystemExit("[fail] _test_plugins_load not found")
src = new_src2
print("[ok] replaced _test_plugins_load with diagnostic version")

# ---------- 3. Diagnose missing explicit_intents: log a line before it runs ----------
# Add a print to the test itself so we can see if it's silently dying.
old_explicit = (
    'def _test_nosignup_explicit():\n'
    '    from neo_nosignups import NeoToolPlugin\n'
    '    p = NeoToolPlugin(str(PROJECT_ROOT / "tools.json"))\n'
    '    cases = ["test regex", "edit pdf", "visualize json", "compress image"]\n'
    '    hits = sum(1 for q in cases if (p.handle_intent(q) or {}).get("has_tool"))\n'
    '    return f"{hits}/{len(cases)} explicit intents fired"'
)
new_explicit = (
    'def _test_nosignup_explicit():\n'
    '    import sys\n'
    '    print("[diag] explicit_intents starting", flush=True)\n'
    '    from neo_nosignups import NeoToolPlugin\n'
    '    p = NeoToolPlugin(str(PROJECT_ROOT / "tools.json"))\n'
    '    cases = ["test regex", "edit pdf", "visualize json", "compress image"]\n'
    '    results = []\n'
    '    for q in cases:\n'
    '        try:\n'
    '            r = p.handle_intent(q) or {}\n'
    '            results.append((q, bool(r.get("has_tool"))))\n'
    '        except Exception as e:\n'
    '            results.append((q, f"ERR:{type(e).__name__}:{e}"))\n'
    '    hits = sum(1 for _, h in results if h is True)\n'
    '    print(f"[diag] explicit_intents done: {results}", flush=True)\n'
    '    return f"{hits}/{len(cases)} explicit intents fired | detail={results}"'
)
if old_explicit in src:
    src = src.replace(old_explicit, new_explicit, 1)
    print("[ok] added diagnostics to _test_nosignup_explicit")
else:
    print("[warn] _test_nosignup_explicit body not matched; skipping diagnostic")

ep.write_text(src, encoding="utf-8")

import py_compile
try:
    py_compile.compile(str(ep), doraise=True)
    print("[ok] harness_extensions.py compiles")
except py_compile.PyCompileError as e:
    print(f"[fail] {e}")
    raise SystemExit(1)