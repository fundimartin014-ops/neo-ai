from pathlib import Path
import py_compile, re

# ============================================================
# FIX 1: colab availability should check ntfy topic too
# ============================================================
vid = Path("core/plugins/video_plugin.py")
src = vid.read_text(encoding="utf-8")

old = '        self._backends["colab"] = bool(self.keys.get("colab"))'
new = ('        self._backends["colab"] = bool(\n'
       '            self.keys.get("colab") or self.keys.get("colab_ntfy")\n'
       '        )')
if old in src:
    src = src.replace(old, new, 1)
    print("[ok] video: colab now available when ntfy topic is set")
elif 'self.keys.get("colab_ntfy")' in src:
    print("[skip] video: colab availability already checks ntfy")
else:
    print("[warn] video: colab availability anchor not found")

vid.write_text(src, encoding="utf-8")
try:
    py_compile.compile(str(vid), doraise=True)
    print("[ok] video_plugin.py compiles")
except py_compile.PyCompileError as e:
    print("[FAIL]", e)
    raise SystemExit(1)

# ============================================================
# FIX 2: /verify and /fast must bypass launcher-level preflights
# ============================================================
lp = Path("launcher.py")
lsrc = lp.read_text(encoding="utf-8")

# 2a. Early return in _handle_factual_query
old_factual = 'def _handle_factual_query(query: str, agent_core=None) -> Optional[str]:\n'
new_factual = (
    'def _handle_factual_query(query: str, agent_core=None) -> Optional[str]:\n'
    '    # Respect /verify and /fast directives — do not intercept them.\n'
    '    _q = (query or "").strip().lower()\n'
    '    if _q.startswith("/verify ") or _q.startswith("/fast "):\n'
    '        return None\n'
)
if old_factual in lsrc and '"/verify "' not in lsrc[:lsrc.find("def _handle_factual_query")+200]:
    lsrc = lsrc.replace(old_factual, new_factual, 1)
    print("[ok] launcher: /verify & /fast bypass factual interception")
elif '"/verify "' in lsrc:
    print("[skip] launcher: already bypasses for /verify")
else:
    print("[warn] launcher: factual anchor not found")

# 2b. Also bypass _try_agents_preflight and plugin preflight for /verify, /fast
# Find _process_chat and inject an early redirect to brain.respond()
proc_anchor = '    def _process_chat(self, message, history=None):\n'
new_proc = (
    '    def _process_chat(self, message, history=None):\n'
    '        # If the user prefixed with /verify or /fast, skip all\n'
    '        # launcher-level pre-flight and let brain.respond() handle it.\n'
    '        _low = (message or "").strip().lower()\n'
    '        if _low.startswith("/verify ") or _low.startswith("/fast "):\n'
    '            try:\n'
    '                import asyncio as _a\n'
    '                try:\n'
    '                    _loop = _a.get_event_loop()\n'
    '                except RuntimeError:\n'
    '                    _loop = _a.new_event_loop()\n'
    '                    _a.set_event_loop(_loop)\n'
    '                _resp = _loop.run_until_complete(self.brain.respond(message))\n'
    '                return {"response": _resp, "model": "verify_mode",\n'
    '                        "mode": "verify", "status": "ok"}\n'
    '            except Exception as _e:\n'
    '                return {"response": f"[verify] {_e}",\n'
    '                        "model": "error", "status": "error"}\n'
)
if proc_anchor in lsrc and '_low.startswith("/verify ")' not in lsrc[:lsrc.find("def _process_chat")+400]:
    lsrc = lsrc.replace(proc_anchor, new_proc, 1)
    print("[ok] launcher: /verify & /fast routed straight to brain")
elif '_low.startswith("/verify ")' in lsrc:
    print("[skip] launcher: /verify routing already present")
else:
    print("[warn] launcher: _process_chat anchor not found")

lp.write_text(lsrc, encoding="utf-8")
try:
    py_compile.compile(str(lp), doraise=True)
    print("[ok] launcher.py compiles")
except py_compile.PyCompileError as e:
    print("[FAIL] launcher:", e)
    raise SystemExit(1)

# ============================================================
# FIX 3: /verify prefix should also apply at the CLI loop
# ============================================================
lsrc2 = lp.read_text(encoding="utf-8")
cli_anchor = (
    '            # FAST PATH: Factual queries\n'
    '            # Agents pre-flight (CLI)\n'
    '            _agents_pre = _try_agents_preflight(user_input, agent_core)'
)
cli_new = (
    '            # /verify and /fast go straight to brain.respond()\n'
    '            _ul = user_input.strip().lower()\n'
    '            if _ul.startswith("/verify ") or _ul.startswith("/fast "):\n'
    '                engine_output = asyncio.run(brain.respond(user_input))\n'
    '                print(engine_output, flush=True)\n'
    '                continue\n'
    '\n'
    '            # FAST PATH: Factual queries\n'
    '            # Agents pre-flight (CLI)\n'
    '            _agents_pre = _try_agents_preflight(user_input, agent_core)'
)
if cli_anchor in lsrc2 and '"/verify "' not in lsrc2[lsrc2.find("FAST PATH: Factual"):lsrc2.find("FAST PATH: Factual")+500]:
    lsrc2 = lsrc2.replace(cli_anchor, cli_new, 1)
    lp.write_text(lsrc2, encoding="utf-8")
    print("[ok] launcher: CLI loop handles /verify & /fast")
elif '"/verify "' in lsrc2:
    print("[skip] launcher: CLI loop already handles /verify")
else:
    print("[warn] launcher: CLI anchor not found")

try:
    py_compile.compile(str(lp), doraise=True)
    print("[ok] launcher.py recompiles")
except py_compile.PyCompileError as e:
    print("[FAIL] launcher:", e)
    raise SystemExit(1)

print()
print("Restart the launcher, then test:")
print("  > generate video of a sunset")
print("  > /verify what is the current price of maize in Kenya?")