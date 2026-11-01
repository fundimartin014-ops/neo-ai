from pathlib import Path

hp = Path("autonomous_test_harness.py")
src = hp.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

# Sanity: harness_extensions.py must exist
if not Path("harness_extensions.py").exists():
    raise SystemExit("[fail] harness_extensions.py missing - run the previous script again")

# --- Bail if already patched ---
already = any("build_extension_tests" in ln for ln in lines)
if already:
    print("[skip] autonomous_test_harness.py already has extension hookup")
    raise SystemExit(0)

# --- 1. Insert extension hookup after the llm.chat test registration ---
out = []
inserted_ext = False
for i, ln in enumerate(lines):
    out.append(ln)
    if not inserted_ext and 'tests.append(TestCase("llm.chat"' in ln:
        out.append("\n")
        out.append("    # --- extension categories: router, nosignup, plugins, memory, orchestrator ---\n")
        out.append("    try:\n")
        out.append("        from harness_extensions import build_extension_tests\n")
        out.append("        tests.extend(build_extension_tests())\n")
        out.append("    except Exception as _e:\n")
        out.append("        print(f\"[harness] extension tests failed to load: {_e}\")\n")
        inserted_ext = True
if not inserted_ext:
    raise SystemExit("[fail] could not find llm.chat registration line")
lines = out

# --- 2. Add --only arg after the --quick arg block ---
out = []
inserted_only = False
i = 0
while i < len(lines):
    out.append(lines[i])
    if (not inserted_only) and 'ap.add_argument("--quick"' in lines[i]:
        # the --quick call spans two physical lines; skip to the end of it
        # (find the closing parenthesis by walking forward)
        j = i + 1
        while j < len(lines) and 'help=' not in lines[j]:
            out.append(lines[j])
            j += 1
        if j < len(lines):
            out.append(lines[j])  # the help= line
        # now insert --only
        out.append('    ap.add_argument("--only", type=str, default=None,\n')
        out.append('                    help="run only tests in this category '
                   '(router|nosignup|plugins|memory|orchestrator|meta|moderouter|...)")\n')
        inserted_only = True
        i = j + 1
        continue
    i += 1
if not inserted_only:
    raise SystemExit("[fail] could not find --quick arg line")
lines = out

# --- 3. Insert filter logic after `tests = build_tests()` line ---
out = []
inserted_filter = False
for ln in lines:
    out.append(ln)
    if (not inserted_filter) and ln.lstrip().startswith("tests = build_tests()"):
        out.append("    if args.only:\n")
        out.append("        tests = [t for t in tests\n")
        out.append("                 if t.category == args.only or t.name.startswith(args.only + \".\")]\n")
        out.append("        if not tests:\n")
        out.append("            print(f\"[harness] no tests matched --only {args.only!r}\")\n")
        out.append("            return 1\n")
        inserted_filter = True
if not inserted_filter:
    raise SystemExit("[fail] could not find tests = build_tests() line")
lines = out

# --- 4. Restructure the registry build block to be conditional ---
# Locate the line that says `print("[harness] building registry` and the
# block that follows through the `print(f"[harness] ... agents registered")` line.
start_idx = None
end_idx = None
for i, ln in enumerate(lines):
    if start_idx is None and "building registry" in ln:
        start_idx = i
    if start_idx is not None and "agents registered" in ln and "len(registry" in ln:
        end_idx = i
        break
if start_idx is None or end_idx is None:
    raise SystemExit("[fail] could not locate registry build block")

# Block we're replacing: from start_idx to end_idx inclusive.
new_block = [
    "    needs_registry = any(t.needs_registry for t in tests)\n",
    "    if not needs_registry:\n",
    "        print(\"[harness] no tests need the agent registry - skipping build\")\n",
    "        db = bus = registry = None\n",
    "    else:\n",
]
# Re-indent the original block by 4 spaces and insert under else:
for k in range(start_idx, end_idx + 1):
    old = lines[k]
    # skip blank lines entirely (keep them but as blanks)
    if old.strip() == "":
        new_block.append("\n")
    else:
        new_block.append("    " + old)
lines = lines[:start_idx] + new_block + lines[end_idx + 1:]

hp.write_text("".join(lines), encoding="utf-8")
print("[ok] patched autonomous_test_harness.py (--only, lazy registry, extension hookup)")

# --- Quick syntax check ---
import py_compile
try:
    py_compile.compile(str(hp), doraise=True)
    print("[ok] syntax check passed")
except py_compile.PyCompileError as e:
    print(f"[fail] syntax error: {e}")
    raise SystemExit(1)
print("[ok] ready: python autonomous_test_harness.py --only router --rounds 1")