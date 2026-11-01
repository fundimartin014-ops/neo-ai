from pathlib import Path
import sys, re

root = Path(".").resolve()

# ============================================================
# 1. Do the device files exist?
# ============================================================
dev = root / "core" / "devices"
print("=" * 64)
print("  core/devices/ contents")
print("=" * 64)
if dev.exists():
    for p in sorted(dev.glob("*")):
        size = p.stat().st_size if p.is_file() else 0
        print(f"  {p.name:<30} {size:>8} bytes")
else:
    print(f"  [MISSING] {dev}")

print()

# ============================================================
# 2. Can we import them?
# ============================================================
print("=" * 64)
print("  Import test")
print("=" * 64)
sys.path.insert(0, str(root))
for mod in ("core.devices", "core.devices.phone", "core.devices.phone_android",
            "core.devices.phone_ios"):
    try:
        __import__(mod)
        print(f"  [ok] {mod}")
    except Exception as e:
        print(f"  [FAIL] {mod}: {type(e).__name__}: {e}")

print()

# ============================================================
# 3. Does _dispatch_prefix exist and what does it return?
# ============================================================
print("=" * 64)
print("  _dispatch_prefix test")
print("=" * 64)
try:
    # Import the function without running main()
    import importlib.util
    spec = importlib.util.spec_from_file_location("_launcher_mod", root / "launcher.py")
    # Don't execute the whole module (it has sys.exit etc at import). Read source instead.
    src = (root / "launcher.py").read_text(encoding="utf-8")

    has_fn = bool(re.search(r"^def _dispatch_prefix\(", src, re.MULTILINE))
    print(f"  _dispatch_prefix defined in launcher.py: {has_fn}")

    # Check CLI loop wiring
    has_cli = "_dispatch_prefix(user_input" in src
    print(f"  Called from CLI loop: {has_cli}")

    # Check HTTP wiring
    has_http = "_dispatch_prefix(message, self.agent_core)" in src
    print(f"  Called from /api/chat: {has_http}")

    # Show the phone branch
    m = re.search(r'if head == "phone":.*?(?=\n    if head ==)', src, re.DOTALL)
    if m:
        print()
        print("  phone branch body:")
        for line in m.group(0).splitlines()[:10]:
            print(f"    {line}")
    else:
        print()
        print("  [WARN] no phone branch found in _dispatch_prefix")
except Exception as e:
    print(f"  [FAIL] {type(e).__name__}: {e}")