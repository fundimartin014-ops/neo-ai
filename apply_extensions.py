from pathlib import Path
import re

root = Path(__file__).resolve().parent

# ============================================================
# 1. Write harness_extensions.py — new test categories
# ============================================================
ext = r"""'''harness_extensions.py - additional test categories covering the whole
Neo stack: routers (launcher preflight, skill preflight, mode router,
reasoning router, nosignup tools), plugins, memory, orchestrator internals.
'''
from __future__ import annotations

import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _TC:
    '''TestCase-compatible object (duck-typed against the main harness).'''
    def __init__(self, name, category, fn, timeout=30.0, needs_registry=False):
        self.name = name
        self.category = category
        self.fn = fn
        self.timeout = timeout
        self.needs_registry = needs_registry


# ---------------------------------------------------------------------------
# Router: skill pre-flight (core/services/neo_brain.py)
# ---------------------------------------------------------------------------
def _test_skill_preflight():
    from core.services.neo_brain import _try_skill_pre_flight
    calls = []
    def mock(**kw):
        calls.append(kw)
        return {"result": f"mocked:{sorted(kw)}"}
    class MockOrch:
        def __init__(self):
            self.plugins = {k: mock for k in (
                "math", "date", "uuid", "text_transform", "translate",
                "language_detect", "levenshtein", "summary", "currency_convert",
            )}
    orch = MockOrch()
    cases = [
        "what is 5*7", "what is 15% of 240", "what is today's date",
        "uuid", "reverse a string hello", "translate hello to swahili",
        "summarize: some text here", "solve x**2 - 4", "100 usd to kes",
    ]
    hits = 0
    for q in cases:
        if _try_skill_pre_flight(q, orch) is not None:
            hits += 1
    if hits < int(len(cases) * 0.7):
        raise RuntimeError(f"only {hits}/{len(cases)} skill routes fired")
    return f"{hits}/{len(cases)} skill routes fired"


def _test_personal_hints():
    from core.services.neo_brain import _is_personal_query
    personal = ["i feel sad", "i think this is hard", "my mom called",
                "should i take the job", "who are you", "what can you do",
                "tell me about yourself"]
    not_personal = ["what is 5*7", "translate hello to swahili",
                    "what is the capital of Kenya", "search: news"]
    ok = sum(1 for q in personal if _is_personal_query(q))
    ok += sum(1 for q in not_personal if not _is_personal_query(q))
    total = len(personal) + len(not_personal)
    if ok < total - 1:
        raise RuntimeError(f"only {ok}/{total} classifications correct")
    return f"{ok}/{total} personal-hint classifications correct"


def _test_mode_router():
    from core.services.neo_brain import ModeRouter
    class FakeLLM: pass
    r = ModeRouter(FakeLLM())
    cases = ["i feel sad today", "what is the weather",
             "search for latest news", "debug this python function"]
    modes = [r.decide_mode(q)["mode"] for q in cases]
    return f"modes: {modes}"


def _test_reasoning_tier():
    from core.meta_cognition import ReasoningRouter, ReasoningTier
    class StubLLM:
        def generate(self, **kw): return None
    rr = ReasoningRouter(StubLLM())
    cases = [
        ("hello", ReasoningTier.FAST),
        ("latest news about kenya", ReasoningTier.RESEARCH),
        ("debug my python function", ReasoningTier.CODING),
        ("summarize this document", ReasoningTier.LONG),
        ("prove this theorem step by step", ReasoningTier.DEEP),
    ]
    hits = 0
    misses = []
    for q, expected in cases:
        got = rr.classify(q)
        if got == expected:
            hits += 1
        else:
            misses.append(f"{q!r}:{got.value}")
    if hits < 4:
        raise RuntimeError(f"{hits}/5 tier classifications (misses: {misses})")
    return f"{hits}/{len(cases)} tiers correct"


def _test_launcher_aliases():
    src = (PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8")
    m = re.search(r"_AGENT_ALIASES\s*=\s*frozenset\(\{(.*?)\}\)", src, re.DOTALL)
    if not m:
        raise RuntimeError("_AGENT_ALIASES not found in launcher.py")
    aliases = set(re.findall(r'"([^"]+)"', m.group(1)))
    expected = {"search", "farm", "market", "summarize", "speak",
                "location", "transcribe", "device", "disease"}
    missing = expected - aliases
    if missing:
        raise RuntimeError(f"missing aliases: {missing}")
    return f"{len(aliases)} aliases, all expected present"


def _test_launcher_vetoes():
    src = (PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8")
    m = re.search(r"_COMPUTE_VETOES\s*=\s*\[(.*?)\]", src, re.DOTALL)
    if not m:
        raise RuntimeError("_COMPUTE_VETOES not found")
    patterns = [re.compile(p) for p in re.findall(r'r"([^"]+)"', m.group(1))]
    cases = [
        ("what is 5 + 3", True),
        ("what is 15% of 240", True),
        ("convert 100 usd to kes", True),
        ("who is the president", False),
        ("what is quantum entanglement", False),
    ]
    hits = 0
    for q, should_veto in cases:
        is_vetoed = any(p.search(q.lower()) for p in patterns)
        if is_vetoed == should_veto:
            hits += 1
    if hits < len(cases):
        raise RuntimeError(f"{hits}/{len(cases)} veto classifications")
    return f"{hits}/{len(cases)} veto classifications correct"


# ---------------------------------------------------------------------------
# No-signup tools (neo_nosignups.py + tools.json)
# ---------------------------------------------------------------------------
def _test_nosignup_stats():
    from neo_nosignups import ToolRegistry
    reg = ToolRegistry(str(PROJECT_ROOT / "tools.json"))
    s = reg.get_stats()
    return (f"{s['total_tools']} tools, {s['total_categories']} categories, "
            f"{s['featured']} featured, {s['iframe_ready']} iframe-ready")


def _test_nosignup_find():
    from neo_nosignups import ToolRegistry
    reg = ToolRegistry(str(PROJECT_ROOT / "tools.json"))
    cases = [
        ("convert pdf to word", "bentopdf"),
        ("draw diagram", "excalidraw"),
        ("test regex", "regexr"),
        ("edit markdown", "stackedit"),
    ]
    hits = 0
    for q, want in cases:
        ids = [m.tool.get("id") for m in reg.find_tool_for_task(q, top_k=3)]
        if want in ids:
            hits += 1
    if hits < 3:
        raise RuntimeError(f"only {hits}/4 find_tool hits")
    return f"{hits}/{len(cases)} top-3 results contained expected tool"


def _test_nosignup_explicit():
    from neo_nosignups import NeoToolPlugin
    p = NeoToolPlugin(str(PROJECT_ROOT / "tools.json"))
    cases = ["test regex", "edit pdf", "visualize json", "compress image"]
    hits = sum(1 for q in cases if (p.handle_intent(q) or {}).get("has_tool"))
    return f"{hits}/{len(cases)} explicit intents fired"


def _test_nosignup_veto():
    from neo_nosignups import NeoToolPlugin
    p = NeoToolPlugin(str(PROJECT_ROOT / "tools.json"))
    cases = ["reverse a string hello", "uppercase foo", "lowercase BAR"]
    ok = sum(1 for q in cases if not (p.handle_intent(q) or {}).get("has_tool"))
    if ok < len(cases):
        raise RuntimeError(f"only {ok}/{len(cases)} text-op vetoes held")
    return f"{ok}/{len(cases)} text-op vetoes held"


def _test_nosignup_integrator():
    from neo_nosignups import ToolRegistry, ToolIntegrator
    reg = ToolRegistry(str(PROJECT_ROOT / "tools.json"))
    integ = ToolIntegrator(reg)
    html = integ.get_iframe_embed("excalidraw", height="400px")
    if not html or "<iframe" not in html:
        raise RuntimeError("iframe embed missing")
    return f"iframe ok, {len(integ.get_quick_actions())} quick actions"


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------
def _test_plugins_load():
    d = PROJECT_ROOT / "core" / "plugins"
    if not d.exists():
        raise RuntimeError("core/plugins missing")
    files = sorted(f for f in d.glob("*.py") if not f.name.startswith("__"))
    loaded, failed = 0, []
    for f in files:
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "Plugin"):
                failed.append(f"{f.name}:no Plugin")
                continue
            mod.Plugin()
            loaded += 1
        except Exception as e:
            failed.append(f"{f.name}:{type(e).__name__}")
    if failed:
        raise RuntimeError(f"{loaded}/{len(files)} loaded; first fail: {failed[0]}")
    return f"{loaded}/{len(files)} plugins loaded"


def _test_plugins_run():
    d = PROJECT_ROOT / "core" / "plugins"
    files = sorted(f for f in d.glob("*.py") if not f.name.startswith("__"))
    ran = 0
    for f in files:
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "Plugin"):
                continue
            p = mod.Plugin()
            if callable(getattr(p, "run", None)):
                p.run()
                ran += 1
        except Exception:
            pass
    return f"{ran} plugins ran their startup hook"


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------
def _test_memory_bridge():
    from core.memory_bridge import NeoMemory
    r = NeoMemory().query("test query", top_k=2)
    if not isinstance(r, dict):
        raise RuntimeError("query did not return dict")
    return f"summary={r.get('summary', '')[:60]!r}"


def _test_memory_unified():
    from core.meta_cognition import UnifiedMemory
    class FakeEmb:
        def store(self, *a, **k): pass
        def search(self, q): return []
    r = UnifiedMemory(FakeEmb()).query("test", top_k=3)
    if not isinstance(r, dict):
        raise RuntimeError("query did not return dict")
    return f"semantic={len(r.get('semantic', []))} structured={len(r.get('structured', []))}"


# ---------------------------------------------------------------------------
# Orchestrator internals
# ---------------------------------------------------------------------------
def _test_orch_construct():
    from core.orchestrator import NeoOrchestrator
    o = NeoOrchestrator(llm_router=None, plugins={}, memory_systems=None, max_iterations=2)
    s = o.get_stats()
    return f"tools={s['tools_available']} neo_tools={s['neo_tool_plugin_active']}"


def _test_orch_prompt_size():
    from core.orchestrator import NeoOrchestrator
    o = NeoOrchestrator(llm_router=None, plugins={}, memory_systems=None, max_iterations=2)
    o.tools = [{"name": f"tool_{i}", "description": "x", "parameters": {}}
               for i in range(100)]
    prompt = o._build_system_prompt()
    approx = len(prompt) // 4
    if approx > 12000:
        raise RuntimeError(f"prompt too large: ~{approx} tokens")
    return f"prompt ~{approx} tokens ({len(prompt)} chars)"


def _test_orch_parse():
    from core.orchestrator import NeoOrchestrator
    o = NeoOrchestrator(llm_router=None, plugins={}, memory_systems=None)
    valid = '{"thought":"need math","action":"math","parameters":{"expression":"5*7"}}'
    call = o._parse_tool_call(valid)
    if call.tool != "math":
        raise RuntimeError(f"parsed wrong tool: {call.tool}")
    if not o._is_tool_call(valid):
        raise RuntimeError("valid tool call not detected")
    if o._is_tool_call("plain text response"):
        raise RuntimeError("false positive on plain text")
    return "parse + detect ok"


# ---------------------------------------------------------------------------
# Meta cognition / personality
# ---------------------------------------------------------------------------
def _test_critique_init():
    from core.meta_cognition import SelfCritique
    class StubLLM:
        def generate(self, **kw): return None
    sc = SelfCritique(StubLLM(), db_path=":memory:")
    return f"patterns={len(sc.get_failure_patterns(min_count=1))} scores={sc.get_recent_scores(limit=5)}"


def _test_personality():
    from core.services.neo_brain import PersonalityEngine
    pe = PersonalityEngine("friendly")
    if not pe.set_personality("mentor"):
        raise RuntimeError("mentor switch failed")
    if not pe.set_personality("strict"):
        raise RuntimeError("strict switch failed")
    if pe.set_personality("nonexistent"):
        raise RuntimeError("invalid personality accepted")
    return "6 profiles, switches + reject ok"


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def build_extension_tests():
    tests = []
    def add(name, cat, fn, timeout=30.0):
        tests.append(_TC(name, cat, fn, timeout=timeout, needs_registry=False))

    add("router.skill_preflight",  "router",     _test_skill_preflight)
    add("router.personal_hints",   "router",     _test_personal_hints)
    add("router.mode_router",      "router",     _test_mode_router)
    add("router.reasoning_tier",   "router",     _test_reasoning_tier)
    add("router.launcher_aliases", "router",     _test_launcher_aliases)
    add("router.launcher_vetoes",  "router",     _test_launcher_vetoes)

    add("nosignup.registry_stats",   "nosignup", _test_nosignup_stats,   timeout=30.0)
    add("nosignup.find_tool",        "nosignup", _test_nosignup_find,    timeout=30.0)
    add("nosignup.explicit_intents", "nosignup", _test_nosignup_explicit)
    add("nosignup.text_op_veto",     "nosignup", _test_nosignup_veto)
    add("nosignup.integrator",       "nosignup", _test_nosignup_integrator)

    add("plugins.load_all", "plugins", _test_plugins_load, timeout=90.0)
    add("plugins.run_hooks", "plugins", _test_plugins_run, timeout=90.0)

    add("memory.bridge_query",  "memory", _test_memory_bridge)
    add("memory.unified_query", "memory", _test_memory_unified)

    add("orchestrator.construct",   "orchestrator", _test_orch_construct, timeout=60.0)
    add("orchestrator.prompt_size", "orchestrator", _test_orch_prompt_size, timeout=30.0)
    add("orchestrator.tool_parse",  "orchestrator", _test_orch_parse, timeout=15.0)

    add("meta.critique_init",  "meta",       _test_critique_init)
    add("moderouter.personality", "moderouter", _test_personality)

    return tests
"""
(root / "harness_extensions.py").write_text(ext, encoding="utf-8")
print("[ok] wrote harness_extensions.py")

# ============================================================
# 2. Patch autonomous_test_harness.py — extend build_tests()
#    and add --only filter + lazy registry
# ============================================================
hp = root / "autonomous_test_harness.py"
src = hp.read_text(encoding="utf-8")

# --- 2a. Extend build_tests() before its final `return tests` ---
anchor = "    tests.append(TestCase(\"llm.chat\", \"llm\", t_llm, timeout=30, needs_registry=False))\n\n    return tests"
if anchor not in src:
    # try windows line endings
    anchor = anchor.replace("\n", "\r\n")
if anchor not in src:
    raise SystemExit("[fail] could not find llm.chat anchor in build_tests()")

replacement = (
    "    tests.append(TestCase(\"llm.chat\", \"llm\", t_llm, timeout=30, needs_registry=False))\n"
    "\n"
    "    # --- extension categories: router, nosignup, plugins, memory, orchestrator ---\n"
    "    try:\n"
    "        from harness_extensions import build_extension_tests\n"
    "        tests.extend(build_extension_tests())\n"
    "    except Exception as _e:\n"
    "        print(f\"[harness] extension tests failed to load: {_e}\")\n"
    "\n"
    "    return tests"
)
if "\r\n" in src and "\r\n" not in replacement:
    replacement = replacement.replace("\n", "\r\n")
src = src.replace(anchor, replacement, 1)

# --- 2b. Add --only arg ---
arg_anchor = "    ap.add_argument(\"--quick\", action=\"store_true\",\n                    help=\"shortcut: 5 minutes, log each test as it runs\")"
if arg_anchor not in src:
    arg_anchor = arg_anchor.replace("\n", "\r\n")
if arg_anchor not in src:
    raise SystemExit("[fail] could not find --quick arg block")

arg_replacement = (
    "    ap.add_argument(\"--quick\", action=\"store_true\",\n"
    "                    help=\"shortcut: 5 minutes, log each test as it runs\")\n"
    "    ap.add_argument(\"--only\", type=str, default=None,\n"
    "                    help=\"run only tests in this category (router|skill|nosignup|plugins|memory|orchestrator|meta|moderouter|agents|...)\")"
)
if "\r\n" in src and "\r\n" not in arg_replacement:
    arg_replacement = arg_replacement.replace("\n", "\r\n")
src = src.replace(arg_anchor, arg_replacement, 1)

# --- 2c. Filter tests + skip registry if not needed ---
filter_anchor = "    tests = build_tests()\n    print(f\"[harness] {len(tests)} tests defined\")"
if filter_anchor not in src:
    filter_anchor = filter_anchor.replace("\n", "\r\n")
if filter_anchor not in src:
    raise SystemExit("[fail] could not find tests=build_tests() line")

filter_replacement = (
    "    tests = build_tests()\n"
    "    if args.only:\n"
    "        tests = [t for t in tests\n"
    "                 if t.category == args.only or t.name.startswith(args.only + \".\")]\n"
    "        if not tests:\n"
    "            print(f\"[harness] no tests matched --only {args.only!r}\")\n"
    "            return 1\n"
    "    print(f\"[harness] {len(tests)} tests defined\" + (f\" (filter={args.only})\" if args.only else \"\"))"
)
if "\r\n" in src and "\r\n" not in filter_replacement:
    filter_replacement = filter_replacement.replace("\n", "\r\n")
src = src.replace(filter_anchor, filter_replacement, 1)

# --- 2d. Skip registry build if no test needs it ---
reg_anchor = (
    "    print(\"[harness] building registry \\u2026\")\n"
    "    from agents.config import Config"
)
if reg_anchor not in src:
    reg_anchor = reg_anchor.replace("\n", "\r\n")
if reg_anchor not in src:
    raise SystemExit("[fail] could not find 'building registry' block")

reg_replacement = (
    "    needs_registry = any(t.needs_registry for t in tests)\n"
    "    if not needs_registry:\n"
    "        print(\"[harness] no tests need the agent registry — skipping build\")\n"
    "        db = bus = registry = None\n"
    "    else:\n"
    "        print(\"[harness] building registry \\u2026\")\n"
    "        from agents.config import Config"
)
if "\r\n" in src and "\r\n" not in reg_replacement:
    reg_replacement = reg_replacement.replace("\n", "\r\n")
src = src.replace(reg_anchor, reg_replacement, 1)

# --- 2e. Fix the rest of the registry build block (needs to be indented now) ---
# The block currently reads:
#   Config.ensure_dirs()
#   async def _build(): ...
#   db, bus, registry = asyncio.run(_build())
#   print(f"[harness] {len(registry.all())} agents registered")
# We need it indented under the else:
# It's tricky to do safely with regex; instead, replace the whole block.
old_block = (
    "    from agents.config import Config\n"
    "    from agents.persistence import Database\n"
    "    from agents.message_bus import MessageBus\n"
    "    from agents.api_server import build_registry\n"
    "\n"
    "    Config.ensure_dirs()\n"
    "    async def _build():\n"
    "        db = Database(Config.DB_PATH)\n"
    "        await db.connect()\n"
    "        bus = MessageBus()\n"
    "        reg = build_registry(bus=bus, db=db)\n"
    "        return db, bus, reg\n"
    "    db, bus, registry = asyncio.run(_build())\n"
    "    print(f\"[harness] {len(registry.all())} agents registered\")"
)
if old_block not in src:
    old_block = old_block.replace("\n", "\r\n")
if old_block not in src:
    # Maybe partial indent from step 2d already happened. Try a softer match.
    print("[warn] full registry block not found as one chunk — trying line-by-line")
else:
    new_block = (
        "        from agents.config import Config\n"
        "        from agents.persistence import Database\n"
        "        from agents.message_bus import MessageBus\n"
        "        from agents.api_server import build_registry\n"
        "        Config.ensure_dirs()\n"
        "        async def _build():\n"
        "            _db = Database(Config.DB_PATH)\n"
        "            await _db.connect()\n"
        "            _bus = MessageBus()\n"
        "            _reg = build_registry(bus=_bus, db=_db)\n"
        "            return _db, _bus, _reg\n"
        "        db, bus, registry = asyncio.run(_build())\n"
        "        print(f\"[harness] {len(registry.all())} agents registered\")"
    )
    if "\r\n" in src and "\r\n" not in new_block:
        new_block = new_block.replace("\n", "\r\n")
    src = src.replace(old_block, new_block, 1)

hp.write_text(src, encoding="utf-8")
print("[ok] patched autonomous_test_harness.py (--only, lazy registry, extensions)")
print("[ok] done — try: python autonomous_test_harness.py --only router --rounds 1")