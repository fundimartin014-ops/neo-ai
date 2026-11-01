from pathlib import Path
import py_compile, re

f = Path("core/devices/phone_android.py")
src = f.read_text(encoding="utf-8")

# Replace _adb_path with a version that falls back to known locations
new_fn = '''def _adb_path():
    # 1. Try PATH first
    p = shutil.which("adb") or shutil.which("adb.exe")
    if p:
        return p
    # 2. Fall back to known install locations (works even if PATH is broken)
    candidates = [
        Path.home() / "Android" / "platform-tools" / "adb.exe",
        Path("C:/Android/platform-tools/adb.exe"),
        Path("C:/platform-tools/adb.exe"),
        Path("C:/Program Files/Android/platform-tools/adb.exe"),
    ]
    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except Exception:
            pass
    return None
'''

# Match the current _adb_path function
pattern = re.compile(
    r"def _adb_path\(\):\n(?:    .*\n|\n)*?(?=\n\n\ndef |\n\ndef )",
    re.MULTILINE,
)

if "Path.home() / \"Android\"" in src:
    print("[skip] _adb_path already has fallback")
else:
    new_src, n = pattern.subn(new_fn + "\n\n\n", src, count=1)
    if n == 0:
        print("[FAIL] could not locate _adb_path function")
        raise SystemExit(1)
    f.write_text(new_src, encoding="utf-8")
    print("[ok] _adb_path now falls back to C:\\Users\\<you>\\Android\\platform-tools\\adb.exe")

try:
    py_compile.compile(str(f), doraise=True)
    print("[ok] phone_android.py compiles")
except py_compile.PyCompileError as e:
    print("[FAIL]", e)
    raise SystemExit(1)

# Show the new function
new_src = f.read_text(encoding="utf-8")
m = re.search(r"def _adb_path\(\):.*?return None", new_src, re.DOTALL)
if m:
    print()
    print("New _adb_path:")
    for line in m.group(0).splitlines():
        print("  " + line)