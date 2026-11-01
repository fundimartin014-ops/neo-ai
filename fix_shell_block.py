from pathlib import Path
import py_compile, re

nb = Path("core/services/neo_brain.py")
lines = nb.read_text(encoding="utf-8").splitlines(keepends=True)

# ============================================================
# 1. Fix indentation of the shell detector block (lines 27..61 approx)
# ============================================================
# Find "# -------- shell-command detector --------"
start = None
end = None
for i, ln in enumerate(lines):
    if "# -------- shell-command detector --------" in ln:
        start = i
    if start is not None and ln.rstrip().endswith(")") and "_SHELL_REPLY" not in ln and i > start:
        # find the closing ) of _SHELL_REPLY
        if "_SHELL_REPLY" in lines[i-5] or any("_SHELL_REPLY" in lines[j] for j in range(max(0,i-10), i)):
            end = i
            break
if start is None or end is None:
    raise SystemExit(f"[fail] shell block not found (start={start}, end={end})")

print(f"[info] shell block: lines {start+1}..{end+1}")

# Known-good replacement (module-level, correct indentation)
good_block = [
    "# -------- shell-command detector --------\n",
    "_SHELL_PREFIXES = (\n",
    '    "python ", "python3 ", "py ",\n',
    '    "pip ", "pip3 ", "npm ", "npx ", "yarn ", "pnpm ",\n',
    '    "docker ", "docker-compose ", "git ",\n',
    '    "cargo ", "rustc ", "go ", "node ",\n',
    '    "uvicorn ", "gunicorn ", "flask ", "django-admin ",\n',
    '    "pytest ", "ruff ", "mypy ",\n',
    '    "curl ", "wget ", "ssh ", "scp ", "rsync ",\n',
    '    "cat ", "ls ", "dir ", "cd ",\n',
    '    "echo ", "touch ", "mkdir ", "rm ", "cp ", "mv ",\n',
    '    "$ ",\n',
    ")\n",
    "\n",
    "\n",
    "def _looks_like_shell_command(text: str) -> bool:\n",
    "    if not text:\n",
    "        return False\n",
    "    low = text.strip().lower()\n",
    "    for p in _SHELL_PREFIXES:\n",
    "        if low.startswith(p.lower()):\n",
    "            return True\n",
    "    if re.search(r\"\\bpython3?\\s+-c\\s+['\\\"]\", text):\n",
    "        return True\n",
    "    return False\n",
    "\n",
    "\n",
    "_SHELL_REPLY = (\n",
    '    "That looks like a shell command. Run it in PowerShell (not here):\\n\\n"\n',
    '    "    {cmd}\\n\\n"\n',
    '    "If you want Neo to execute shell commands for you, use:\\n"\n',
    '    "    > agent run shell: {cmd}\\n"\n',
    '    "(that routes to SystemAgent, which runs commands locally)"\n',
    ")\n",
]

lines = lines[:start] + good_block + lines[end+1:]
print("[ok] shell detector block replaced with correct indentation")

# ============================================================
# 2. Wire the short-circuit into respond()
# ============================================================
# Pattern: after the "self.conversation_history.append({"role": "user"...})" line
# inside respond(), before the URL learning comment.
pat = re.compile(
    r'^(        self\.conversation_history\.append\(\{"role": "user", "content": user_input\}\)\n)'
    r'(\n+)'
    r'(        # --- URL learning fast path)',
    re.MULTILINE,
)

short_circuit = (
    "\n"
    "        # --- shell-command short-circuit -----------------------------------\n"
    "        if _looks_like_shell_command(user_input):\n"
    "            reply = _SHELL_REPLY.format(cmd=user_input.strip())\n"
    "            self.conversation_history.append({\n"
    "                \"role\": \"assistant\", \"content\": reply,\n"
    "                \"mode\": \"SHELL_HINT\", \"personality\": \"professional\",\n"
    "            })\n"
    "            return self._format_response(\n"
    "                reply,\n"
    "                {\"mode\": \"SHELL_HINT\", \"personality\": \"professional\"},\n"
    "            )\n"
    "\n"
)

src = "".join(lines)
m = pat.search(src)
if m:
    # Replace group1 + group2 + group3 with group1 + short_circuit + group3
    src = src[:m.start()] + m.group(1) + short_circuit + m.group(3) + src[m.end(3):]
    print("[ok] short-circuit wired into respond()")
else:
    print("[warn] respond() prologue pattern not matched")
    # Show what we have
    idx = src.find('self.conversation_history.append({"role": "user"')
    if idx >= 0:
        print("--- surrounding lines ---")
        print(src[idx:idx+400])

nb.write_text(src, encoding="utf-8")

# ============================================================
# 3. Compile
# ============================================================
try:
    py_compile.compile(str(nb), doraise=True)
    print("[ok] neo_brain.py compiles")
except py_compile.PyCompileError as e:
    print(f"[fail] {e}")
    # Show surrounding lines
    m = re.search(r"line (\d+)", str(e))
    if m:
        line_no = int(m.group(1))
        new_lines = Path("core/services/neo_brain.py").read_text(encoding="utf-8").splitlines()
        for i in range(max(0, line_no-4), min(len(new_lines), line_no+4)):
            print(f"  {i+1:4d}: {new_lines[i]!r}")
    raise SystemExit(1)

print()
print("Test now:  python -c \"print('hi')\"   at the Neo prompt")
print("Should return a one-line shell hint without calling the LLM.")