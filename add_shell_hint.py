from pathlib import Path
import py_compile, re

root = Path(".").resolve()
nb = root / "core" / "services" / "neo_brain.py"
src = nb.read_text(encoding="utf-8")

# ---------- 1. shell-command detector + short-circuit ----------
detector_impl = '''

# -------- shell-command detector --------
_SHELL_PREFIXES = (
    "python ", "python3 ", "py ",
    "pip ", "pip3 ", "npm ", "npx ", "yarn ", "pnpm ",
    "docker ", "docker-compose ", "git ",
    "cargo ", "rustc ", "go ", "node ",
    "uvicorn ", "gunicorn ", "flask ", "django-admin ",
    "pytest ", "ruff ", "mypy ",
    "curl ", "wget ", "ssh ", "scp ", "rsync ",
    "cat ", "ls ", "dir ", "cd ",
    "echo ", "touch ", "mkdir ", "rm ", "cp ", "mv ",
    "$ ",
)


def _looks_like_shell_command(text: str) -> bool:
    if not text:
        return False
    low = text.strip().lower()
    for p in _SHELL_PREFIXES:
        if low.startswith(p.lower()):
            return True
    if re.search(r"\\bpython3?\\s+-c\\s+['\\"]", text):
        return True
    return False


_SHELL_REPLY = (
    "That looks like a shell command. Run it in PowerShell (not here):\\n\\n"
    "    {cmd}\\n\\n"
    "If you want Neo to execute shell commands for you, use:\\n"
    "    > agent run shell: {cmd}\\n"
    "(that routes to SystemAgent, which runs commands locally)"
)
'''
if "_looks_like_shell_command" not in src:
    anchor = (
        '    async def respond(self, user_input: str) -> str:\n'
        '        self.total_calls += 1\n'
        '        self.conversation_history.append({"role": "user", "content": user_input})\n'
    )
    if anchor in src:
        src = src.replace(anchor, anchor + detector_impl, 1)
        # wire it right after the conversation_history append
        wire_anchor = (
            '        self.conversation_history.append({"role": "user", "content": user_input})\n'
            '\n'
            '        # --- URL learning fast path'
        )
        wire_new = (
            '        self.conversation_history.append({"role": "user", "content": user_input})\n'
            '\n'
            '        # --- shell-command short-circuit ---\n'
            '        if _looks_like_shell_command(user_input):\n'
            '            reply = _SHELL_REPLY.format(cmd=user_input.strip())\n'
            '            self.conversation_history.append({\n'
            '                "role": "assistant", "content": reply,\n'
            '                "mode": "SHELL_HINT", "personality": "professional",\n'
            '            })\n'
            '            return self._format_response(\n'
            '                reply,\n'
            '                {"mode": "SHELL_HINT", "personality": "professional"},\n'
            '            )\n'
            '\n'
            '        # --- URL learning fast path'
        )
        if wire_anchor in src:
            src = src.replace(wire_anchor, wire_new, 1)
            print("[ok] shell detector + short-circuit wired")
        else:
            print("[warn] URL anchor not found — short-circuit not wired")
    else:
        print("[warn] respond() anchor not found")
else:
    print("[skip] shell detector already present")

# ---------- 2. /fast and /verify prefixes ----------
old_verify = '        _mode = os.getenv("NEO_REASONING_MODE", "").lower()\n        if _mode == "verify" and not _is_personal_query(user_input):'
new_verify = (
    '        _user_low = user_input.strip().lower()\n'
    '        _force_fast = _user_low.startswith("/fast ")\n'
    '        _force_verify = _user_low.startswith("/verify ")\n'
    '        if _force_fast:\n'
    '            user_input = user_input[6:].strip()\n'
    '        elif _force_verify:\n'
    '            user_input = user_input[8:].strip()\n'
    '        _mode = os.getenv("NEO_REASONING_MODE", "").lower()\n'
    '        _use_verify = _force_verify or (_mode == "verify" and not _force_fast)\n'
    '        if _use_verify and not _is_personal_query(user_input):'
)
if old_verify in src:
    src = src.replace(old_verify, new_verify, 1)
    print("[ok] /fast and /verify prefixes added")
elif "/fast " in src and "/verify " in src:
    print("[skip] prefixes already present")
else:
    print("[warn] verification check not found")

nb.write_text(src, encoding="utf-8")

# ---------- 3. .env.example warning ----------
env_ex = root / ".env.example"
existing = env_ex.read_text(encoding="utf-8") if env_ex.exists() else ""
old_reasoning = """# ============ Reasoning mode ============
# NEO_REASONING_MODE=verify
#   Every non-skill query goes through:
#     decompose -> draft -> critique -> revise -> confidence
#   Slower (3-5 LLM calls per query) but self-checked.
#   Leave unset for the current fast path.
# NEO_REASONING_MODE="""
new_reasoning = """# ============ Reasoning mode ============
# NEO_REASONING_MODE=verify
#
#   WARNING: multiplies LLM calls by 4-5x per query. Free-tier providers
#   (Groq ~30/min, OpenRouter 20/min) will rate-limit fast. Enable only
#   when you need the extra check.
#
#   Per-query override:
#       /fast <question>    -> single-call fast path
#       /verify <question>  -> force the verification loop
#
# NEO_REASONING_MODE="""
if old_reasoning in existing:
    existing = existing.replace(old_reasoning, new_reasoning, 1)
    env_ex.write_text(existing, encoding="utf-8")
    print("[ok] .env.example updated with cost warning")
else:
    print("[skip] .env.example reasoning block unchanged")

# ---------- 4. compile ----------
try:
    py_compile.compile(str(nb), doraise=True)
    print("[ok] neo_brain.py compiles")
except py_compile.PyCompileError as e:
    print(f"[fail] {e}")
    raise SystemExit(1)

print()
print("Restart launcher. Try at the Neo prompt:")
print('  python -c "print(1)"')
print("Expected: one-line hint, no LLM calls.")
print()
print("Then decide on verification mode:")
print("  (a) keep NEO_REASONING_MODE=verify  (max quality, burns quota)")
print("  (b) remove that line                (fast by default, /verify to opt in)")
print("  Recommend (b) given the 429s in your log.")