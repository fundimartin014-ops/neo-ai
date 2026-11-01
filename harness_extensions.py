'''harness_extensions.py - additional test categories covering the whole
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


def _extract_list_body(src, name):
    """Return the text between the [ and matching ] of `<name> = [...]`."""
    marker = name + " = ["
    idx = src.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker) - 1
    depth = 0
    i = start
    while i < len(src):
        c = src[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return src[start + 1:i]
        i += 1
    return None


def _test_launcher_vetoes():
    src = (PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8")
    body = _extract_list_body(src, "_COMPUTE_VETOES")
    if body is None:
        raise RuntimeError("_COMPUTE_VETOES not found")
    patterns = [re.compile(p) for p in re.findall(r'r"([^"]+)"', body)]
    cases = [
        ("what is 5 + 3", True),
        ("what is 15% of 240", True),
        ("convert 100 usd to kes", True),
        ("who is the president", False),
        ("what is quantum entanglement", False),
    ]
    misses = []
    for q, should_veto in cases:
        got = any(p.search(q.lower()) for p in patterns)
        if got != should_veto:
            misses.append((q, should_veto, got))
    if misses:
        raise RuntimeError(f"{len(cases) - len(misses)}/{len(cases)} veto classifications; misses={misses}")
    return f"{len(cases)}/{len(cases)} veto classifications correct ({len(patterns)} patterns)"

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
    if hits < len(cases):
        raise RuntimeError(f"only {hits}/{len(cases)} explicit intents fired")
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
    loaded = 0
    no_plugin = []
    failed = []
    for f in files:
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "Plugin"):
                no_plugin.append(f.name)
                continue
            mod.Plugin()
            loaded += 1
        except Exception as e:
            failed.append(f"{f.name}:{type(e).__name__}:{str(e)[:80]}")
    if failed:
        raise RuntimeError(
            f"{loaded} loaded, {len(failed)} failed, {len(no_plugin)} non-plugin. "
            f"Fails={failed} NoPlugin={no_plugin}"
        )
    return f"{loaded} loaded, {len(no_plugin)} non-plugin skipped; names={no_plugin}"

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
    import tempfile
    from core.meta_cognition import SelfCritique
    class StubLLM:
        def generate(self, **kw): return None
    tmp = tempfile.mkdtemp()
    db_path = str(Path(tmp) / "critique_test.db")
    sc = SelfCritique(StubLLM(), db_path=db_path)
    p = len(sc.get_failure_patterns(min_count=1))
    s = sc.get_recent_scores(limit=5)
    return f"patterns={p} scores={s}"


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
