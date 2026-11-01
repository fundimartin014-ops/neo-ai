from pathlib import Path
import py_compile, re

lp = Path("launcher.py")
src = lp.read_text(encoding="utf-8")

# ============================================================
# 1. Add _dispatch_prefix function right after _try_plugin_preflight
# ============================================================
if "_dispatch_prefix(" not in src:
    dispatcher = '''

def _dispatch_prefix(text, agent_core=None):
    """Direct dispatch for <prefix>: <payload>.

    Runs at the TOP of every query path (CLI loop and /api/chat),
    before plugin/agent/factual preflights. Returns a result string,
    or None if the prefix is not one we handle.
    """
    stripped = (text or "").strip()
    if ":" not in stripped:
        return None
    head, _, payload = stripped.partition(":")
    head = head.strip().lower()
    payload = payload.strip()

    # ---- direct handlers (no orchestrator needed) ----
    if head == "phone":
        try:
            from core.devices.phone import handle as _h
            return _h(payload)
        except Exception as e:
            return f"[phone] {type(e).__name__}: {e}"

    if head == "cameras":
        try:
            from core.cameras.frigate import sync_to_store, FrigateClient
            from core.geo import store as _store
            p = payload.lower()
            if p in ("sync", "refresh"):
                return str(sync_to_store())
            if p in ("status", "online"):
                return str(FrigateClient().version())
            if p in ("list", "cams", "cameras"):
                cams = FrigateClient().cameras()
                return "Frigate cameras: " + (", ".join(cams) if cams else "(none)")
            if p.startswith("add "):
                parts = payload.split(None, 2)
                if len(parts) < 3:
                    return "Usage: cameras: add <name> <url> [lat] [lng]"
                _, name, rest = parts
                url_parts = rest.split()
                url = url_parts[0]
                lat = float(url_parts[1]) if len(url_parts) > 1 else None
                lng = float(url_parts[2]) if len(url_parts) > 2 else None
                c = _store.add_camera(name, "rtsp", url, lat, lng)
                return f"[cameras] added {name} ({c['id'][:6]})"
            return "Usage: cameras: sync | status | list | add <name> <url> [lat] [lng]"
        except Exception as e:
            return f"[cameras] {type(e).__name__}: {e}"

    if head == "home":
        try:
            from core.devices.home_assistant import HomeAssistant
            return HomeAssistant().handle(payload)
        except Exception as e:
            return f"[home] {type(e).__name__}: {e}"

    if head == "sim":
        try:
            from core.driving.sim_bridge import handle as _h
            return _h(payload)
        except Exception as e:
            return f"[sim] {type(e).__name__}: {e}"

    # ---- plugin-backed handlers (need orchestrator) ----
    if head in ("sms", "report"):
        orch = (agent_core or {}).get("orchestrator")
        if not orch:
            return None
        plugins = getattr(orch, "plugins", {}) or {}
        if head == "sms":
            pl = plugins.get("sms_plugin") or plugins.get("sms")
        else:
            pl = plugins.get("report_plugin") or plugins.get("report")
        if not pl:
            return f"[{head}] plugin not loaded"
        try:
            return str(pl.process(payload))
        except Exception as e:
            return f"[{head}] {type(e).__name__}: {e}"

    return None

'''
    anchor = "def _try_plugin_preflight(message, agent_core):"
    if anchor not in src:
        raise SystemExit("[fail] _try_plugin_preflight anchor not found")
    # Insert BEFORE _try_plugin_preflight
    src = src.replace(anchor, dispatcher.lstrip("\n") + "\n" + anchor, 1)
    print("[ok] inserted _dispatch_prefix")
elif "def _dispatch_prefix(" in src:
    print("[skip] _dispatch_prefix already present")

lp.write_text(src, encoding="utf-8")

# ============================================================
# 2. CLI loop: call _dispatch_prefix at the top of each iteration
# ============================================================
src = lp.read_text(encoding="utf-8")

cli_anchor = (
    '            if "[neo]" in low or "[vision]" in low or "[launcher]" in low or "batches:" in low:\n'
    '                continue\n'
)
cli_insert = cli_anchor + (
    '\n'
    '            # Direct prefix dispatch — runs before everything else\n'
    '            try:\n'
    '                _prefix_res = _dispatch_prefix(user_input, agent_core)\n'
    '                if _prefix_res is not None:\n'
    '                    print(_prefix_res, flush=True)\n'
    '                    continue\n'
    '            except Exception as _e:\n'
    '                print(f"[prefix] {type(_e).__name__}: {_e}", flush=True)\n'
    '                continue\n'
)

if cli_anchor in src and "_dispatch_prefix(user_input" not in src:
    src = src.replace(cli_anchor, cli_insert, 1)
    print("[ok] CLI loop calls _dispatch_prefix")
elif "_dispatch_prefix(user_input" in src:
    print("[skip] CLI loop already calls _dispatch_prefix")
else:
    print("[warn] CLI anchor not found")

# ============================================================
# 3. /api/chat: call _dispatch_prefix right after /verify check
# ============================================================
proc_anchor = (
    '    def _process_chat(self, message, history=None):\n'
    '        # If the user prefixed with /verify or /fast, skip all\n'
    '        # launcher-level pre-flight and let brain.respond() handle it.\n'
)
proc_insert = (
    '    def _process_chat(self, message, history=None):\n'
    '        # Direct prefix dispatch (phone:, cameras:, home:, sim:, sms:, report:)\n'
    '        try:\n'
    '            _prefix_res = _dispatch_prefix(message, self.agent_core)\n'
    '            if _prefix_res is not None:\n'
    '                return {"response": _prefix_res, "model": "prefix",\n'
    '                        "mode": "direct", "status": "ok"}\n'
    '        except Exception:\n'
    '            pass\n'
    '\n'
    '        # If the user prefixed with /verify or /fast, skip all\n'
    '        # launcher-level pre-flight and let brain.respond() handle it.\n'
)

if proc_anchor in src and "_dispatch_prefix(message, self.agent_core)" not in src:
    src = src.replace(proc_anchor, proc_insert, 1)
    print("[ok] /api/chat calls _dispatch_prefix")
elif "_dispatch_prefix(message, self.agent_core)" in src:
    print("[skip] /api/chat already calls _dispatch_prefix")
else:
    print("[warn] _process_chat anchor not found")

lp.write_text(src, encoding="utf-8")

# ============================================================
# 4. Compile
# ============================================================
try:
    py_compile.compile(str(lp), doraise=True)
    print("[ok] launcher.py compiles")
except py_compile.PyCompileError as e:
    print("[FAIL]", e)
    raise SystemExit(1)

print()
print("Restart the launcher, then test:")
print("  > phone: status")
print("  > phone: battery")
print("  > cameras: status")
print("  > home: status")
print("  > sim: connect")