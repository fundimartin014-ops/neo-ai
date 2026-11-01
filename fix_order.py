from pathlib import Path

hp = Path("autonomous_test_harness.py")
lines = hp.read_text(encoding="utf-8").splitlines(keepends=True)

# Find the two anchor lines
needs_reg_idx = None
tests_start = None
tests_end = None

for i, ln in enumerate(lines):
    if needs_reg_idx is None and "needs_registry = any(t.needs_registry for t in tests)" in ln:
        needs_reg_idx = i
    if tests_start is None and ln.lstrip().startswith("tests = build_tests()"):
        tests_start = i
    if tests_start is not None and tests_end is None and "[harness] {len(tests)} tests defined" in ln:
        tests_end = i

if needs_reg_idx is None or tests_start is None or tests_end is None:
    raise SystemExit(f"[fail] anchors: needs={needs_reg_idx} start={tests_start} end={tests_end}")

if tests_start < needs_reg_idx:
    print("[skip] tests block already before needs_registry check")
    raise SystemExit(0)

# Extract the tests+filter+print block
tests_block = lines[tests_start:tests_end + 1]
# Remove it from its current position
remaining = lines[:tests_start] + lines[tests_end + 1:]

# Recompute where needs_registry lives in the remaining list
needs_reg_idx2 = None
for i, ln in enumerate(remaining):
    if "needs_registry = any(t.needs_registry for t in tests)" in ln:
        needs_reg_idx2 = i
        break
if needs_reg_idx2 is None:
    raise SystemExit("[fail] needs_registry anchor vanished")

# Insert the tests block BEFORE the needs_registry line
new_lines = remaining[:needs_reg_idx2] + tests_block + remaining[needs_reg_idx2:]

hp.write_text("".join(new_lines), encoding="utf-8")
print("[ok] hoisted tests = build_tests() above the needs_registry check")

# Syntax check
import py_compile
try:
    py_compile.compile(str(hp), doraise=True)
    print("[ok] syntax check passed")
except py_compile.PyCompileError as e:
    print(f"[fail] syntax error: {e}")
    raise SystemExit(1)