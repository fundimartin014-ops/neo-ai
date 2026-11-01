from pathlib import Path
import re

lp = Path("launcher.py")
src = lp.read_text(encoding="utf-8")

# ---------- 1. Add _PLUGIN_PREFIXES + _try_plugin_preflight after _try_agents_preflight ----------
anchor = (
    'def _warmup_agents_skill(agent_core) -> None:'
)
new_block = r'''_PLUGIN_PREFIXES = {
    "sms":    ("sms_plugin",    "sms"),
    "report": ("report_plugin", "report"),
}


def _try_plugin_preflight(message, agent_core):
    """Route '<plugin>: <payload>' straight to a plugin's process().

    Currently handles sms: and report:. These aren't agents, so they can't
    go through agents_skill. They ARE loaded as plugins in the orchestrator,
    so we dispatch directly.
    """
    stripped = (message or "").strip()
    if ":" not in stripped:
        return None
    head, _, tail = stripped.partition(":")
    head = head.strip().lower()
    entry = _PLUGIN_PREFIXES.get(head)
    if not entry:
        return None
    orch = (agent_core or {}).get("orchestrator")
    if orch is None:
        return None
    plugins = getattr(orch, "plugins", {}) or {}
    plugin = None
    for key in entry:
        if key in plugins:
            plugin = plugins[key]
            break
    if plugin is None:
        return None
    payload = _strip_outer_quotes(tail)
    try:
        if hasattr(plugin, "process"):
            return str(plugin.process(payload))
        if hasattr(plugin, "handle"):
            return str(plugin.handle(payload))
        if hasattr(plugin, "run"):
            return str(plugin.run(payload))
        return f"[{head}] plugin has no process/handle/run method"
    except Exception as e:
        return f"[{head}] {type(e).__name__}: {e}"


'''
if anchor not in src:
    raise SystemExit("[fail] _warmup_agents_skill anchor not found")
if "_try_plugin_preflight" in src:
    print("[skip] plugin preflight already present")
else:
    src = src.replace(anchor, new_block + anchor, 1)
    print("[ok] inserted _try_plugin_preflight into launcher.py")

# ---------- 2. Call it in _process_chat, before _try_agents_preflight ----------
old_call = (
    '        # Agents pre-flight — route \'alias: payload\' to skills/agents_skill.py\n'
    '        agents_result = _try_agents_preflight(message, self.agent_core)'
)
new_call = (
    '        # Plugin pre-flight — sms:, report: etc. go to orchestrator.plugins directly\n'
    '        plugin_result = _try_plugin_preflight(message, self.agent_core)\n'
    '        if plugin_result:\n'
    '            return {"response": plugin_result, "model": "plugin_runtime",\n'
    '                    "mode": "plugin", "status": "ok"}\n'
    '\n'
    '        # Agents pre-flight — route \'alias: payload\' to skills/agents_skill.py\n'
    '        agents_result = _try_agents_preflight(message, self.agent_core)'
)
if old_call in src:
    src = src.replace(old_call, new_call, 1)
    print("[ok] hooked plugin preflight into /api/chat")
elif "plugin_result = _try_plugin_preflight" in src:
    print("[skip] /api/chat already calls plugin preflight")
else:
    print("[warn] could not find _process_chat hook point — manual edit needed")

# ---------- 3. Add to CLI loop, before the agents preflight there ----------
cli_old = (
    '            # FAST PATH: Factual queries\n'
    '            # Agents pre-flight (CLI)\n'
    '            _agents_pre = _try_agents_preflight(user_input, agent_core)'
)
cli_new = (
    '            # Plugin pre-flight (CLI)\n'
    '            _plugin_pre = _try_plugin_preflight(user_input, agent_core)\n'
    '            if _plugin_pre:\n'
    '                print(_plugin_pre)\n'
    '                continue\n'
    '\n'
    '            # FAST PATH: Factual queries\n'
    '            # Agents pre-flight (CLI)\n'
    '            _agents_pre = _try_agents_preflight(user_input, agent_core)'
)
if cli_old in src:
    src = src.replace(cli_old, cli_new, 1)
    print("[ok] hooked plugin preflight into CLI loop")
elif "_plugin_pre = _try_plugin_preflight" in src:
    print("[skip] CLI loop already calls plugin preflight")
else:
    print("[warn] could not find CLI hook point — manual edit needed")

lp.write_text(src, encoding="utf-8")

# ---------- 4. Sanity compile ----------
import py_compile
try:
    py_compile.compile(str(lp), doraise=True)
    print("[ok] launcher.py compiles")
except py_compile.PyCompileError as e:
    print(f"[fail] {e}")
    raise SystemExit(1)