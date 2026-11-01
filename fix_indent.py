from pathlib import Path
import re, py_compile

vp = Path("core/plugins/vision_plugin.py")
src = vp.read_text(encoding="utf-8")

# Delete the two orphaned if-lines entirely
for fake in ("veida", "kavel"):
    src = re.sub(
        rf'^[ \t]*if bid == "{fake}":.*?\r?\n',
        '',
        src, flags=re.MULTILINE,
    )

# Also confirm they're filtered out of backend_order
if "REMOVED" in src:
    print("[info] removing dangling # REMOVED comments")
    src = re.sub(r'[ \t]*# REMOVED[ \t]*\r?\n', '\n', src)

vp.write_text(src, encoding="utf-8")

try:
    py_compile.compile(str(vp), doraise=True)
    print("[ok] vision_plugin.py compiles")
except py_compile.PyCompileError as e:
    print(f"[FAIL] {e}")
    # Print the failing block for diagnosis
    m = re.search(r"line (\d+)", str(e))
    if m:
        ln = int(m.group(1))
        lines = Path("core/plugins/vision_plugin.py").read_text(encoding="utf-8").splitlines()
        for i in range(max(0, ln-5), min(len(lines), ln+5)):
            print(f"  {i+1:4d}: {lines[i]!r}")
    raise SystemExit(1)