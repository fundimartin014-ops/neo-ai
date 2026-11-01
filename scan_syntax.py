import ast
import sys
from pathlib import Path

root = Path("agents")
bad = []
for p in sorted(root.rglob("*.py")):
    try:
        src = p.read_text(encoding="utf-8")
        ast.parse(src, filename=str(p))
    except SyntaxError as e:
        bad.append((str(p), e.lineno, e.msg, (e.text or "").rstrip()))

if not bad:
    print("OK: no syntax errors")
    sys.exit(0)

print(f"FOUND {len(bad)} file(s) with syntax errors:\n")
for path, line, msg, text in bad:
    print(f"  {path}:{line}")
    print(f"    msg : {msg}")
    print(f"    line: {text}")
    print()
sys.exit(1)