from pathlib import Path
import re

api = Path("agents/api_server.py")
src = api.read_text(encoding="utf-8")

# 1. Strip any previous KnowledgeAgent lines (import + register)
src = re.sub(r"^[ \t]*from agents\.knowledge_agent import KnowledgeAgent.*\r?\n",
             "", src, flags=re.MULTILINE)
src = re.sub(r"^[ \t]*(reg|registry)\.register\(KnowledgeAgent\(\)\).*\r?\n",
             "", src, flags=re.MULTILINE)

# 2. Find the def build_registry(...) signature line
sig = re.search(r"def build_registry\([^\n]*\)[^\n]*:[ \t]*\r?\n", src)
if not sig:
    raise SystemExit("[fail] cannot find def build_registry(...)")

# 3. Insert import right after the signature (so name is defined)
import_line = "    from agents.knowledge_agent import KnowledgeAgent  # patched\n"
src = src[:sig.end()] + import_line + src[sig.end():]

# 4. Find the FIRST line that creates the registry (reg = FooRegistry(...))
init = re.search(
    r"^([ \t]*)(reg|registry)\s*=\s*\w*Registry\([^\n]*\)[ \t]*\r?\n",
    src, re.MULTILINE,
)
if not init:
    # Fallback: any `reg = ...` assignment inside build_registry
    init = re.search(r"^([ \t]*)(reg|registry)\s*=[^\n]*\r?\n", src, re.MULTILINE)
if not init:
    raise SystemExit("[fail] cannot find reg/registry initialization line")

indent, var = init.group(1), init.group(2)
register_line = f"{indent}{var}.register(KnowledgeAgent())  # patched\n"
src = src[:init.end()] + register_line + src[init.end():]

api.write_text(src, encoding="utf-8")
print(f"[ok] inserted import after signature and {var}.register(KnowledgeAgent()) after init line")