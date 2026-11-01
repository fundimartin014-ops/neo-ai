from pathlib import Path
import re

api = Path("agents/api_server.py")
src = api.read_text(encoding="utf-8")

# 1. Strip any previous KnowledgeAgent lines (idempotent)
src = re.sub(r"^[ \t]*from agents\.knowledge_agent import KnowledgeAgent[ \t]*\r?\n",
             "", src, flags=re.MULTILINE)
src = re.sub(r"^[ \t]*(reg|registry)\.register\(KnowledgeAgent\(\)\)[ \t]*\r?\n",
             "", src, flags=re.MULTILINE)

# 2. Find the build_registry signature (handles type hints / arrows)
m = re.search(r"def build_registry\([^\n]*\)[^\n]*:[ \t]*\r?\n", src)
if not m:
    raise SystemExit("[fail] could not locate def build_registry(...) signature")

# 3. Inject import + register right after the signature line,
#    so the name is defined before first use.
inject = (
    "    # KnowledgeAgent (added by patch)\n"
    "    from agents.knowledge_agent import KnowledgeAgent\n"
    "    reg.register(KnowledgeAgent())\n"
)
src = src[:m.end()] + inject + src[m.end():]

api.write_text(src, encoding="utf-8")
print("[ok] agents/api_server.py — KnowledgeAgent import + register placed at top of build_registry")