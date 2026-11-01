#!/usr/bin/env python3
"""
launcher.py — NEO V8 UNIFIED + Hybrid Merger Integration
Updated August 2026: 2,249 cloud models, hybrid merge engine, dark web panel.
"""

import re
import os
import sys
import traceback
import importlib.util
import logging
import shutil
import asyncio
import threading
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional

MODE_WEB = "--web" in sys.argv
MODE_DESKTOP = "--desktop" in sys.argv
MODE_SERVER = "--server" in sys.argv
MODE_TEST_KEYS = "--test-keys" in sys.argv

PROJECT_ROOT = Path(__file__).parent.resolve()
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))
sys.dont_write_bytecode = True

# ═══════════════════════════════════════════════════════════════════
# AGGRESSIVE CACHE PURGE
# ═══════════════════════════════════════════════════════════════════

def _clear_python_cache():
    count_dirs = 0
    count_files = 0
    for root, dirs, files in os.walk(PROJECT_ROOT, topdown=True):
        for d in list(dirs):
            if d == '__pycache__':
                p = Path(root) / d
                try:
                    shutil.rmtree(p)
                    count_dirs += 1
                    dirs.remove(d)
                except Exception:
                    pass
        for f in files:
            if f.endswith('.pyc') or f.endswith('.pyo'):
                try:
                    os.remove(Path(root) / f)
                    count_files += 1
                except Exception:
                    pass
    if count_dirs or count_files:
        print(f"[Launcher] Cleared {count_dirs} cache dirs, {count_files} bytecode files")

_clear_python_cache()

_MODULES_TO_PURGE = [
    'fundibrain', 'brain', 'orchestrator', 'local_llm', 'llm_router',
    'memory_bridge', 'persistent_index', 'vision_plugin', 'tavily_search',
    'research_agent', 'serper_search', 'meta_cognition', 'system_scanner',
    'neo_brain', 'reasoning_planner', 'neo_model_manager', 'hybrid_ui',
    'hybrid_merger', 'neo_models_catalog'
]
for mod in list(sys.modules.keys()):
    if any(p in mod for p in _MODULES_TO_PURGE):
        del sys.modules[mod]

try:
    from dotenv import load_dotenv
    env_paths = [PROJECT_ROOT / ".env", PROJECT_ROOT / "core" / ".env"]
    for p in env_paths:
        if p.exists():
            load_dotenv(str(p), override=True)
            print(f"[Launcher] Loaded .env from: {p}")
            break
except ImportError:
    print("[Launcher] python-dotenv not installed")

import os as _os_ml
_os_ml.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
_os_ml.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
_os_ml.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# NEO MODEL MANAGER + HYBRID UI (NEW)
# ═══════════════════════════════════════════════════════════════════

try:
    from neo_model_manager import NeoModelManager, get_model_manager
    from hybrid_ui import register_hybrid_routes
    NEO_MM_AVAILABLE = True
except ImportError as e:
    print(f"[Launcher] Neo Model Manager not available: {e}")
    NEO_MM_AVAILABLE = False
    NeoModelManager = None
    get_model_manager = None
    register_hybrid_routes = None

# ═══════════════════════════════════════════════════════════════════
# API KEY VALIDATOR
# ═══════════════════════════════════════════════════════════════════
def test_all_apis():
    print("\n" + "=" * 64)
    print("  NEO API KEY VALIDATOR — August 2026 Model IDs")
    print("=" * 64 + "\n")
    results = {}

    # Tavily
    tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
    if tavily_key:
        try:
            from core.tavily_search import tavily_search
            r = tavily_search("hello world", search_depth="basic", max_results=1)
            print("  ✅ Tavily        — WORKING")
            results["tavily"] = True
        except Exception as e:
            print(f"  ❌ Tavily        — FAILED: {e}")
            results["tavily"] = False
    else:
        print("  ⚠️  Tavily        — KEY MISSING")
        results["tavily"] = None

    # Groq
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        groq_models = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3.6-27b"]
        groq_ok = False
        for model in groq_models:
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                    timeout=15,
                )
                if r.status_code == 200:
                    print(f"  ✅ Groq          — WORKING (model: {model})")
                    groq_ok = True
                    break
            except Exception as e:
                print(f"  ❌ Groq          — ERROR: {e} (model: {model})")
        if not groq_ok:
            print("      → Groq 403 = account suspended, free tier exhausted, or region blocked.")
        results["groq"] = groq_ok
    else:
        print("  ⚠️  Groq          — KEY MISSING")
        results["groq"] = None

    # OpenRouter
    or_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if or_key:
        or_models = [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
            "qwen/qwen3.8-27b:free",
            "cohere/north-mini-code:free",
            "liquid/lfm-2.5-2.6b:free",
        ]
        or_ok = False
        for model in or_models:
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {or_key}", "HTTP-Referer": "https://neo-ai.local", "X-Title": "Neo AI", "Content-Type": "application/json"},
                    json={"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                    timeout=15,
                )
                if r.status_code == 200:
                    print(f"  ✅ OpenRouter    — WORKING (model: {model})")
                    or_ok = True
                    break
            except Exception as e:
                print(f"  ❌ OpenRouter    — ERROR: {e} (model: {model})")
        if not or_ok:
            print("      → Free model IDs rotated. Run the probe script to list current ones.")
        results["openrouter"] = or_ok
    else:
        print("  ⚠️  OpenRouter    — KEY MISSING")
        results["openrouter"] = None

    # Moonshot
    moon_key = os.getenv("MOONSHOT_API_KEY", "").strip()
    if moon_key:
        try:
            r = requests.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={"Authorization": f"Bearer {moon_key}", "Content-Type": "application/json"},
                json={"model": "moonshot-v1-8k", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                timeout=15,
            )
            if r.status_code == 200:
                print("  ✅ Moonshot      — WORKING")
                results["moonshot"] = True
            else:
                print(f"  ❌ Moonshot      — HTTP {r.status_code}")
                results["moonshot"] = False
        except Exception as e:
            print(f"  ❌ Moonshot      — ERROR: {e}")
            results["moonshot"] = False
    else:
        print("  ⚠️  Moonshot      — KEY MISSING")
        results["moonshot"] = None

    # Replicate
    rep_key = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if rep_key:
        try:
            r = requests.get(
                "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell",
                headers={"Authorization": f"Token {rep_key}"},
                timeout=10,
            )
            if r.status_code == 200:
                print("  ✅ Replicate     — WORKING")
                results["replicate"] = True
            else:
                print(f"  ❌ Replicate     — HTTP {r.status_code}")
                results["replicate"] = False
        except Exception as e:
            print(f"  ❌ Replicate     — ERROR: {e}")
            results["replicate"] = False
    else:
        print("  ⚠️  Replicate     — KEY MISSING")
        results["replicate"] = None

    # Ollama
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"  ✅ Ollama        — WORKING ({', '.join(models)})")
            results["ollama"] = True
        else:
            print(f"  ❌ Ollama        — HTTP {r.status_code}")
            results["ollama"] = False
    except Exception as e:
        print(f"  ❌ Ollama        — ERROR: {e}")
        results["ollama"] = False

    print("\n" + "=" * 64)
    working = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    missing = sum(1 for v in results.values() if v is None)
    print(f"  RESULTS:  Working {working}  |  Failed {failed}  |  Missing {missing}")
    print("=" * 64 + "\n")
    return results

# =====================================================================
# FACTUAL QUERY BYPASS
# =====================================================================
# ---------------------------------------------------------------------------
# Agents pre-flight — routes "alias: payload" to skills/agents_skill.py
# ---------------------------------------------------------------------------
_AGENT_ALIASES = frozenset({
    "search", "summarize", "summary", "farm", "brief", "market",
    "scheduler", "schedule", "web", "fetch", "file", "files",
    "system", "shell", "knowledge", "sentiment", "validate",
    "notify", "notification", "tag", "tagging", "task", "profile", "memory",
    "disease", "diagnose", "image_analysis", "analyze_image",
    "transcribe", "voice",
    "location",
    "speak", "tts",
    "sms", "report",
    "device", "iot",
})


def _strip_outer_quotes(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("\"", "'"):
        return s[1:-1].strip()
    return s


def _find_agents_tool(agent_core):
    """Locate our agents skill (or its LazyTool wrapper) in the plugin registry."""
    if not agent_core:
        return None
    orch = agent_core.get("orchestrator")
    if not orch:
        return None
    plugins = getattr(orch, "plugins", {}) or {}
    for key in ("agents", "agents_skill", "agent"):
        if key in plugins:
            return plugins[key]
    for name, t in plugins.items():
        spec = getattr(t, "spec", None) or {}
        if "agents_skill" in str(spec.get("module_path", "")):
            return t
    return None


def _try_agents_preflight(message, agent_core):
    """
    If `message` is '<alias>: <payload>' and <alias> is a known agents alias,
    call the agents skill and return its result. Otherwise return None so the
    original pipeline runs unchanged.
    """
    stripped = (message or "").strip()
    if ":" not in stripped:
        return None
    head, _, tail = stripped.partition(":")
    head = head.strip().lower()
    if head not in _AGENT_ALIASES:
        return None
    # Rebuild the query with outer quotes stripped from the payload
    rebuilt = f"{head}: {_strip_outer_quotes(tail)}"
    tool = _find_agents_tool(agent_core)
    if tool is None:
        return None
    try:
        if callable(tool):
            result = tool(query=rebuilt)
        else:
            return None
        if result is None:
            return None
        return str(result)
    except Exception as e:
        return f"[Agents] {e}"


_PLUGIN_PREFIXES = {
    "sms":     ("sms_plugin",     "sms"),
    "report":  ("report_plugin",  "report"),
    # camera / device / driving — dispatched to dedicated handler functions
    "cameras": ("__cameras__",    "cameras"),
    "home":    ("__home__",       "home"),
    "sim":     ("__sim__",        "sim"),
}


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
    # --- special handlers that don't go through orchestrator.plugins
    if head in ("cameras", "home", "sim"):
        payload = _strip_outer_quotes(tail)
        if head == "cameras":
            try:
                from core.cameras.frigate import sync_to_store, FrigateClient
                from core.geo import store as _geo_store
                low = payload.lower()
                if low in ("sync", "refresh"):
                    return str(sync_to_store())
                if low in ("status", "online"):
                    return str(FrigateClient().version())
                if low in ("list", "cams", "cameras"):
                    cams = FrigateClient().cameras()
                    return "Frigate cameras: " + (", ".join(cams) if cams else "(none)")
                if low.startswith("add "):
                    parts = payload.split(None, 2)
                    if len(parts) < 3:
                        return "Usage: cameras: add <name> <rtsp-url> [lat] [lng]"
                    _, name, rest = parts
                    url_parts = rest.split()
                    url = url_parts[0]
                    lat = float(url_parts[1]) if len(url_parts) > 1 else None
                    lng = float(url_parts[2]) if len(url_parts) > 2 else None
                    c = _geo_store.add_camera(name, "rtsp", url, lat, lng)
                    return f"[cameras] added {name} ({c[chr(39)+chr(105)+chr(100)+chr(39)] if False else c['id'][:6]})"
                return ("Usage: cameras: sync | status | list | "
                        "add <name> <rtsp-url> [lat] [lng]")
            except Exception as _e:
                return f"[cameras] {type(_e).__name__}: {_e}"
        if head == "home":
            try:
                from core.devices.home_assistant import HomeAssistant
                return HomeAssistant().handle(payload)
            except Exception as _e:
                return f"[home] {type(_e).__name__}: {_e}"
        if head == "sim":
            try:
                from core.driving.sim_bridge import handle as sim_handle
                return sim_handle(payload)
            except Exception as _e:
                return f"[sim] {type(_e).__name__}: {_e}"

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


def _warmup_agents_skill(agent_core) -> None:
    """Kick off the agents skill boot in the background so the first user
    request doesn't pay the 30-60s registry-load cost."""
    import threading
    def _boot():
        try:
            tool = _find_agents_tool(agent_core)
            if tool is None:
                return
            # Call with no args to trigger _ensure_booted() but not run anything
            try:
                _ = tool(query="")
            except Exception:
                pass
        except Exception:
            pass
    threading.Thread(target=_boot, name="AgentsSkillWarmup", daemon=True).start()


def _handle_factual_query(query: str, agent_core=None) -> Optional[str]:
    # Respect /verify and /fast directives — do not intercept them.
    _q = (query or "").strip().lower()
    if _q.startswith("/verify ") or _q.startswith("/fast "):
        return None
    # --- FIXED: Veto compute / convert / date queries. Previously the
    # trigger list below matched "what is 15% of 240" and "what is today's
    # date", hijacking them for Tavily. Those are compute/date requests that
    # should route through NeoOrchestrator so math/date/convert skills fire.
    # The veto patterns are narrow — genuine factual queries ("who is the
    # president of Kenya", "what is quantum entanglement") still fall through
    # to Tavily below.
    q_lower_pre = query.lower()
    _COMPUTE_VETOES = [
        r"\b\d+\s*%\s*of\b",                         # "15% of 240"
        r"\b\d+\s*[+\-*/]\s*\d+",                    # "5 + 3", "10 * 2"
        r"\bconvert\s+\d",                           # "convert 100 usd"
        r"\b(calculate|compute|multiply|divide|subtract)\b",
        r"\b(today|tomorrow|yesterday)(?:'s)?\s+(date|day)\b",
        r"^\s*(uuid|random|fibonacci)\b",
        r"^\s*reverse\s+a?\s*string",
        # ADDED: block Tavily for self-referential + command queries
        r"^\s*who\s+are\s+you\s*\??\s*$",
        r"^\s*what\s+are\s+you\s*\??\s*$",
        r"^\s*what\s+is\s+your\s+name\s*\??\s*$",
        r"^\s*what\s+can\s+you\s+do\s*\??\s*$",
        r"^\s*tell\s+me\s+about\s+yourself",
        r"^\s*train\s+",
        r"^\s*https?://",
    ]
    if any(re.search(pat, q_lower_pre) for pat in _COMPUTE_VETOES):
        return None
    # --- end FIXED ---

    triggers = [
        r"\b(who is|who are|who was|who were)\b",
        r"\b(what is|what are|what was|what were)\b",
        r"\b(when did|when was|when are)\b",
        r"\b(where is|where was|where are)\b",
        r"\b(why did|why is|why are)\b",
        r"\b(how many|how much|how old|how tall|how big)\b",
        r"\b(current|latest|today|now|recent)\b",
        r"\b(president|prime minister|king|queen|ceo|founder|mayor)\b",
        r"\b(price|cost|worth|value|stock)\b",
        r"\b(weather|temperature|forecast)\b",
        r"\b(population|capital|currency|language|gdp)\b",
        r"\b(news|headlines|breaking)\b",
        r"\b(definition|meaning of|define)\b",
    ]
    q = query.lower()
    if not any(re.search(p, q) for p in triggers):
        return None
    # Try agents runtime first (search: is our SearchAgent)
    if agent_core is not None:
        _agents_tool = _find_agents_tool(agent_core)
        if _agents_tool is not None:
            try:
                _res = _agents_tool(query=f"search: {query}")
                if _res and not str(_res).startswith("[Tool error"):
                    return str(_res)
            except Exception:
                pass

    try:
        from core.tavily_search import tavily_search
        result = tavily_search(query, search_depth="basic", max_results=5, include_answer=True)
        if isinstance(result, dict):
            return result.get('answer') or (result.get('results', [{}])[0].get('content', str(result)) if result.get('results') else str(result))
        return str(result) if result else None
    except Exception as e:
        logger.warning(f"[FactualBypass] Tavily failed: {e}")
        return None

# =====================================================================
# PLUGIN LOADER
# =====================================================================
def load_plugins():
    folder = PROJECT_ROOT / "core" / "plugins"
    loaded = []
    if not folder.exists():
        logger.warning(f"[Launcher] Plugin folder not found: {folder}")
        return loaded
    for f in folder.glob("*.py"):
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "Plugin"):
                loaded.append(mod.Plugin())
                logger.info(f"[Launcher] Loaded: {f.name}")
        except Exception as e:
            logger.error(f"[Launcher] Failed {f.name}: {e}")
    return loaded

# =====================================================================
# LLM INITIALIZER
# =====================================================================
def init_llm():
    try:
        from core.local_llm import LocalLLM
    except ImportError as e:
        logger.error(f"[Neo] Cannot import LocalLLM: {e}")
        return None
    logger.info("[Neo] Initializing LLM...")
    try:
        llm = LocalLLM(model="qwen2.5:1.5b")
        if llm._ollama_ready:
            logger.info("[Neo] LLM initialized (Ollama fallback ready)")
        if llm.groq_key or llm.or_key or llm.moon_key or llm.replicate_key:
            logger.info("[Neo] Cloud keys loaded (will be tested on first call)")
        return llm
    except Exception as e:
        logger.error(f"[Neo] LLM init failed: {e}")
        return None

# =====================================================================
# AGENT CORE
# =====================================================================
def init_agent_core(plugins):
    logger.info("[Neo] Initializing Agent Core...")
    try:
        from core.llm_router import LLMRouter
        from core.orchestrator import NeoOrchestrator
        from core.persistent_index import PersistentFAISS
        from core.memory_bridge import NeoMemory

        llm_router = LLMRouter(use_local_llm=True)
        logger.info("[Neo] LLM Router active")

        vector_store = PersistentFAISS(dimension=384)
        stats = vector_store.get_stats() if hasattr(vector_store, "get_stats") else {"total_vectors": 0}
        logger.info(f"[Neo] Vector store: {stats.get('total_vectors', 0)} vectors loaded")

        plugin_dict = {}
        for p in plugins:
            mod_name = getattr(p, "__module__", "")
            if mod_name:
                name = mod_name.split(".")[-1]
            else:
                raw = p.__class__.__name__.lower()
                name = raw.replace('plugin', '').replace('trainer', '').rstrip('_')
                if not name:
                    name = raw
            plugin_dict[name] = p
            logger.info(f"[Launcher] Plugin mapped: {name}")
            # Only these plugins run in the background. Everything else
            # uses only run() (called earlier in the startup-hooks loop).
            _BACKGROUND_PLUGINS = {"farm_scheduler_plugin", "irrigation_alert_plugin"}
            if name in _BACKGROUND_PLUGINS and hasattr(p, "start") and callable(getattr(p, "start")):
                try:
                    p.start()
                except Exception as _e:
                    logger.warning("[Launcher] %s.start() failed: %s", name, _e)

        memory = NeoMemory(vector_store=vector_store, relational_db=None)
        orchestrator = NeoOrchestrator(llm_router=llm_router, plugins=plugin_dict, memory_systems=memory, max_iterations=5)
        logger.info("[Neo] Agent Orchestrator active")
        logger.info(f"[Neo] Tool catalog: {len(orchestrator.tools)} tools mapped")

        # ═══ LAZY-WIRE SKILLS / AGENTS / CORE MODULES ═══
        try:
            from core.tool_loader import register_lazy_tools
            result = register_lazy_tools(orchestrator, PROJECT_ROOT)
            logger.info(
                f"[Neo] Lazy tools: {result['registered']} registered "
                f"({result['collisions']} renamed, {result['skipped']} skipped)"
            )
            logger.info(f"[Neo] Final tool catalog: {len(orchestrator.tools)} tools")
        except Exception as e:
            logger.warning(f"[Neo] Lazy tool registration failed: {e}")
        # ═══ END LAZY-WIRE ═══

        return {"llm_router": llm_router, "orchestrator": orchestrator, "memory": memory, "vector_store": vector_store}
    except Exception as e:
        logger.error(f"[Neo] Agent core init failed: {e}")
        traceback.print_exc()
        return None

# =====================================================================
# BRAIN INITIALIZER
# =====================================================================
def init_brain(plugins, llm, agent_core=None):
    candidates = [("fundibrain", "FundiBrain"), ("core.brain", "FundiBrain")]
    brain = None
    for mod_name, cls_name in candidates:
        try:
            module = __import__(mod_name, fromlist=[cls_name])
            FundiBrainClass = getattr(module, cls_name)
            try:
                fundibrain = FundiBrainClass(plugins=plugins, mini_llm=llm)
            except TypeError:
                fundibrain = FundiBrainClass()
            logger.info(f"[Neo] FundiBrain loaded from {mod_name}.{cls_name}")
            from core.services.neo_brain import wrap_fundibrain
            orch = agent_core.get("orchestrator") if agent_core else None
            brain = wrap_fundibrain(fundibrain, llm, orchestrator=orch)
            logger.info("[Neo] NeoBrain wrapper active")
            if orch:
                logger.info("[Neo] Agent mode: ENABLED")
            logger.info("[Neo] Modes: PERSONAL | HYBRID | TOOL_ASSISTED | AGENT")
            logger.info("[Neo] Personalities: friendly | professional | strict | mentor | analyst | creative")
            break
        except Exception as e:
            logger.warning(f"[Neo] Import failed for {mod_name}.{cls_name}: {e}")
    if brain is None:
        raise ImportError("Could not initialize FundiBrain.")
    return brain

# =====================================================================
# EMBEDDED API SERVER
# =====================================================================
API_HOST = os.getenv("NEO_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("NEO_API_PORT", "8000"))

class NeoAPIServer:
    def __init__(self, brain, agent_core, llm):
        self.brain = brain
        self.agent_core = agent_core
        self.llm = llm
        self.app = None
        self.thread = None
        self.mm = None
        self._setup()

    def _setup(self):
        try:
            from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
            from flask_cors import CORS
        except ImportError:
            logger.error("[API] Flask not installed. Run: pip install flask flask-cors")
            return

        self.app = Flask(__name__, static_folder=str(PROJECT_ROOT))
        CORS(self.app, resources={r"/api/*": {"origins": "*"}})

        # ═══ REGISTER HYBRID ROUTES (NEW) ═══
        if NEO_MM_AVAILABLE and register_hybrid_routes:
            try:
                self.mm = get_model_manager()
                register_hybrid_routes(self.app, model_manager=self.mm)
                logger.info("[Neo] Hybrid UI routes registered at /hybrid")
            except Exception as e:
                logger.error(f"[Neo] Failed to register hybrid routes: {e}")

        # ═══ REGISTER SCHEDULER UI (NEW) ═══
        try:
            from scheduler_ui import register_scheduler_routes
            register_scheduler_routes(self.app, agent_core=self.agent_core)
        except Exception as e:
            logger.warning(f"[Neo] scheduler UI not registered: {e}")

        # ═══ REGISTER MAP UI (NEW) ═══
        try:
            from map_ui import register_map_routes
            register_map_routes(self.app, agent_core=self.agent_core)
            logger.info("[Neo] Map UI routes registered at /map")
        except Exception as e:
            logger.warning(f"[Neo] map UI not registered: {e}")


        # ═══ SERVE /reports/* (PDF report downloads) ═══
        @self.app.route("/reports/<path:fname>")
        def _reports(fname):
            from flask import send_from_directory
            p = PROJECT_ROOT / "generated_reports"
            if not p.exists():
                return jsonify({"error": "no reports yet"}), 404
            return send_from_directory(str(p), fname)


        @self.app.route("/")
        def index():
            ui_path = PROJECT_ROOT / "neo_chat.html"
            if ui_path.exists():
                with open(ui_path, "r", encoding="utf-8") as f:
                    html = f.read()
                inject = (
                    '<script src="/static/quick_panel.js" defer></script>\n'
                    '<script src="/static/gesture.js" defer></script>\n'
                    '<script src="/static/speak.js" defer></script>'
                )
                if "quick_panel.js" not in html:
                    if "</body>" in html:
                        html = html.replace("</body>", inject + "\n</body>", 1)
                    else:
                        html += inject
                return html, 200, {"Content-Type": "text/html"}
            return jsonify({"error": "neo_chat.html not found"}), 404

        @self.app.route("/static/<path:fname>")
        def _static(fname):
            from flask import send_from_directory
            return send_from_directory(str(PROJECT_ROOT / "static"), fname)

        @self.app.route("/farm")
        def farm_dashboard():
            from flask import send_from_directory
            fp = PROJECT_ROOT / "farm.html"
            if fp.exists():
                return send_from_directory(str(PROJECT_ROOT), "farm.html", mimetype="text/html")
            return "farm.html missing", 404

        @self.app.route("/api/health")
        def health():
            profile = "unknown"
            try:
                from agents.profiles import active_profile
                profile = active_profile()
            except Exception:
                pass
            return jsonify({
                "status": "ok",
                "brain": bool(self.brain),
                "orchestrator": bool(self.agent_core and self.agent_core.get("orchestrator")),
                "llm": bool(self.llm),
                "hybrid": NEO_MM_AVAILABLE,
                "agent_profile": profile,
                "timestamp": datetime.now().isoformat(),
            })

        @self.app.route("/api/profile")
        def profile_api():
            try:
                from agents.profiles import active_profile, allowed_aliases, describe
                allowed = allowed_aliases()
                return jsonify({
                    "active": active_profile(),
                    "description": describe(),
                    "allowed": sorted(allowed) if allowed else ["*"],
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/stats")
        def stats():
            if not self.brain:
                return jsonify({"error": "Brain not initialized"}), 503
            try:
                return jsonify(self.brain.get_stats())
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/models")
        def models():
            """Return active cloud models from Neo Model Manager."""
            if NEO_MM_AVAILABLE and self.mm:
                picks = self.mm.get_quick_picks("chat", limit=50)
                return jsonify({
                    "models": [
                        {"id": m["name"], "provider": m["provider"], "tier": m.get("tier", ""), "type": m["type"], "context": m["ctx"]}
                        for m in picks
                    ],
                    "total_catalog": self.mm.get_stats()["total_catalog"],
                    "active_models": self.mm.get_stats()["active_models"],
                    "source": "neo_model_manager"
                })
            # Fallback to hardcoded list
            return jsonify({
                "models": [
                    {"id": "openai/gpt-oss-120b", "provider": "groq", "tier": "fast", "context": 131072},
                    {"id": "nvidia/nemotron-3-super-120b-a12b:free", "provider": "openrouter", "tier": "chat", "context": 262144},
                    {"id": "google/gemma-4-31b-it:free", "provider": "openrouter", "tier": "chat", "context": 262144},
                ],
                "source": "fallback"
            })

        @self.app.route("/api/chat", methods=["POST"])
        def chat():
            data = request.get_json() or {}
            message = data.get("message", "").strip()
            history = data.get("history", [])
            stream = data.get("stream", False)
            if not message:
                return jsonify({"error": "Empty message"}), 400
            if stream:
                return Response(stream_with_context(self._stream_chat(message, history)), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
            return jsonify(self._process_chat(message, history))

        @self.app.route("/api/agent", methods=["POST"])
        def agent():
            data = request.get_json() or {}
            query = data.get("query", "").strip()
            history = data.get("history", [])
            if not query:
                return jsonify({"error": "Empty query"}), 400
            orch = self.agent_core.get("orchestrator") if self.agent_core else None
            if not orch:
                return jsonify({"error": "Agent orchestrator not available"}), 503
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            response = loop.run_until_complete(orch.run(query, history))
            return jsonify({"response": response, "model": "agent_orchestrator", "mode": "agent"})

        @self.app.route("/api/research", methods=["POST"])
        def research():
            data = request.get_json() or {}
            query = data.get("query", "").strip()
            if not query:
                return jsonify({"error": "Empty query"}), 400
            try:
                from core.tavily_search import tavily_search
                result = tavily_search(query, search_depth="advanced", max_results=5, include_answer=True)
                return jsonify({"response": result, "model": "tavily_research", "mode": "research"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        # ─── VISION API ROUTES ─────────────────────────────────────
        @self.app.route("/api/vision/generate", methods=["POST"])
        def vision_generate():
            data = request.get_json() or {}
            prompt = data.get("prompt", "").strip()
            width = data.get("width", 1024)
            height = data.get("height", 768)
            seed = data.get("seed")
            if not prompt:
                return jsonify({"error": "prompt is required"}), 400
            orch = self.agent_core.get("orchestrator") if self.agent_core else None
            vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
            if not vision:
                return jsonify({"error": "vision_plugin not loaded"}), 503
            result = vision.generate(prompt, width, height, seed)
            if result.startswith("[Vision Error]"):
                return jsonify({"error": result}), 500
            filepath = result.replace("[Vision] Image generated: ", "").strip()
            filename = os.path.basename(filepath)
            return jsonify({"status": "ok", "prompt": prompt, "file_path": filepath, "filename": filename, "url": f"/images/{filename}"})

        @self.app.route("/api/vision/describe", methods=["POST"])
        def vision_describe():
            data = request.get_json() or {}
            image_path = data.get("image_path", "").strip()
            prompt = data.get("prompt", "Describe this image.")
            if not image_path:
                return jsonify({"error": "image_path is required"}), 400
            orch = self.agent_core.get("orchestrator") if self.agent_core else None
            vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
            if not vision:
                return jsonify({"error": "vision_plugin not loaded"}), 503
            result = vision.describe(image_path, prompt)
            if result.startswith("[Vision Error]"):
                return jsonify({"error": result}), 500
            return jsonify({"status": "ok", "description": result})

        @self.app.route("/images/<path:filename>")
        def serve_image(filename):
            orch = self.agent_core.get("orchestrator") if self.agent_core else None
            vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
            if vision and hasattr(vision, "temp_dir") and os.path.exists(os.path.join(vision.temp_dir, filename)):
                return send_from_directory(vision.temp_dir, filename)
            return jsonify({"error": "Image not found"}), 404

    def _process_chat(self, message, history=None):
        # Direct prefix dispatch (phone:, cameras:, home:, sim:, sms:, report:)
        try:
            _prefix_res = _dispatch_prefix(message, self.agent_core)
            if _prefix_res is not None:
                return {"response": _prefix_res, "model": "prefix",
                        "mode": "direct", "status": "ok"}
        except Exception:
            pass

        # If the user prefixed with /verify or /fast, skip all
        # launcher-level pre-flight and let brain.respond() handle it.
        _low = (message or "").strip().lower()
        if _low.startswith("/verify ") or _low.startswith("/fast "):
            try:
                import asyncio as _a
                try:
                    _loop = _a.get_event_loop()
                except RuntimeError:
                    _loop = _a.new_event_loop()
                    _a.set_event_loop(_loop)
                _resp = _loop.run_until_complete(self.brain.respond(message))
                return {"response": _resp, "model": "verify_mode",
                        "mode": "verify", "status": "ok"}
            except Exception as _e:
                return {"response": f"[verify] {_e}",
                        "model": "error", "status": "error"}
        if not self.brain:
            return {"response": "[Neo] Brain not initialized.", "model": "error", "status": "error"}

        msg_lower = message.lower().strip()

        # ─── API generate fast path ───
        if msg_lower.startswith("generate "):
            prompt = message[9:].strip()
            if not prompt:
                return {"response": "Usage: generate <prompt> [width] [height] [backend=<name>]", "model": "vision", "status": "error"}
            backend = None
            if "backend=" in prompt.lower():
                m = re.search(r'backend=(\w+)', prompt, re.IGNORECASE)
                if m:
                    backend = m.group(1).lower()
                    prompt = re.sub(r'\s*backend=\w+\s*', ' ', prompt, flags=re.IGNORECASE).strip()
            parts = prompt.split()
            width, height = 1024, 768
            if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
                width, height = int(parts[-2]), int(parts[-1])
                prompt = " ".join(parts[:-2])
            elif len(parts) >= 2 and parts[-1].isdigit():
                width = height = int(parts[-1])
                prompt = " ".join(parts[:-1])
            orch = self.agent_core.get("orchestrator") if self.agent_core else None
            vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
            if not vision:
                return {"response": "[Neo] Vision plugin not loaded.", "model": "error", "status": "error"}
            result = vision.generate(prompt, width, height, model_hint=backend)
            return {"response": result, "model": "vision_plugin", "status": "ok"}

        # ─── API describe fast path ───
        if msg_lower.startswith("describe "):
            path = message[9:].strip()
            if not path:
                return {"response": "Usage: describe <image_path>", "model": "vision", "status": "error"}
            orch = self.agent_core.get("orchestrator") if self.agent_core else None
            vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
            if not vision:
                return {"response": "[Neo] Vision plugin not loaded.", "model": "error", "status": "error"}
            result = vision.describe(path)
            return {"response": result, "model": "vision_plugin", "status": "ok"}

        # Plugin pre-flight — sms:, report: etc. go to orchestrator.plugins directly
        plugin_result = _try_plugin_preflight(message, self.agent_core)
        if plugin_result:
            return {"response": plugin_result, "model": "plugin_runtime",
                    "mode": "plugin", "status": "ok"}

        # Agents pre-flight — route 'alias: payload' to skills/agents_skill.py
        agents_result = _try_agents_preflight(message, self.agent_core)
        if agents_result:
            return {"response": agents_result, "model": "agents_runtime", "mode": "agents", "status": "ok"}

        factual = _handle_factual_query(message, self.agent_core)
        if factual:
            return {"response": factual, "model": "agents_search", "mode": "factual", "status": "ok"}

        try:
            if message.lower().startswith("agent "):
                query = message[6:].strip()
                agent_lower = query.lower()
                image_prefixes = ["draw ", "paint ", "sketch ", "generate an image", "generate a picture", "create an image", "create a picture", "make an image", "make a picture", "image of ", "picture of "]
                if any(agent_lower.startswith(p) for p in image_prefixes):
                    orch = self.agent_core.get("orchestrator") if self.agent_core else None
                    vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
                    if vision:
                        prompt = query
                        for prefix in image_prefixes:
                            if prompt.lower().startswith(prefix):
                                prompt = prompt[len(prefix):]
                                break
                        result = vision.generate(prompt.strip())
                        return {"response": result, "model": "vision_flux", "mode": "agent_image", "status": "ok"}
                orch = self.agent_core.get("orchestrator") if self.agent_core else None
                if orch:
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    response = loop.run_until_complete(orch.run(query, history or []))
                    return {"response": response, "model": "agent_orchestrator", "mode": "agent"}
            if message.lower().startswith("research "):
                from core.tavily_search import tavily_search
                query = message[9:].strip()
                result = tavily_search(query, search_depth="advanced", max_results=5, include_answer=True)
                return {"response": result, "model": "tavily_research", "mode": "research"}
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            response = loop.run_until_complete(self.brain.respond(message))
            return {"response": response, "model": "unknown", "status": "ok", "mode": "standard"}
        except Exception as e:
            traceback.print_exc()
            return {"response": f"[Neo] Error: {str(e)}", "model": "error", "status": "error"}

    def _stream_chat(self, message, history=None):
        import time
        if not self.brain:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Brain not initialized'})}\n\n"
            return
        try:
            result = self._process_chat(message, history)
            response = result.get("response", "")
            model = result.get("model", "unknown")
            yield f"data: {json.dumps({'type': 'model', 'model': model})}\n\n"
            words = response.split(" ")
            buffer = ""
            for i, word in enumerate(words):
                buffer += word + " "
                if i % 3 == 0 or i == len(words) - 1:
                    yield f"data: {json.dumps({'type': 'token', 'content': buffer})}\n\n"
                    buffer = ""
                    time.sleep(0.03)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    def start(self):
        if not self.app:
            logger.error("[API] Flask app not initialized")
            return False
        self.thread = threading.Thread(target=self.app.run, kwargs={"host": API_HOST, "port": API_PORT, "debug": False, "threaded": True, "use_reloader": False}, daemon=True)
        self.thread.start()
        logger.info(f"[API] Server started at http://{API_HOST}:{API_PORT}")
        if NEO_MM_AVAILABLE:
            logger.info(f"[API] Hybrid panel at http://{API_HOST}:{API_PORT}/hybrid")
        return True

# =====================================================================
# PYWEBVIEW DESKTOP APP
# =====================================================================
def launch_desktop(api_url):
    try:
        import webview
    except ImportError:
        print("[Desktop] PyWebView not installed. Falling back to browser...")
        import webbrowser
        webbrowser.open(api_url)
        return
    window = webview.create_window("Neo AI — Personal Intelligence", api_url, width=1200, height=800, min_size=(800, 600), text_select=True, confirm_close=True)
    webview.start(debug=False)

# =====================================================================
# MAIN
# =====================================================================
def main():
    if MODE_TEST_KEYS:
        test_all_apis()
        return

    for d in ["data/vector_store", "data", "logs", "temp/spreadsheets", "generated_images"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("[Launcher] Directories ready")

    plugins = load_plugins()
    logger.info(f"[Launcher] Total plugins: {len(plugins)}")

    logger.info("[Launcher] Running plugin startup hooks...")
    for plugin in plugins:
        try:
            if hasattr(plugin, "run"):
                plugin.run()
        except Exception as e:
            logger.error(f"[Plugin Error] {e}")

    llm = init_llm()
    agent_core = init_agent_core(plugins)

    # Give plugins a chance to grab agent_core (used by farm_scheduler_plugin)
    for _plugin in plugins:
        if hasattr(_plugin, "on_agent_core"):
            try:
                _plugin.on_agent_core(agent_core)
            except Exception as _e:
                logger.warning(
                    "[Launcher] on_agent_core failed for %s: %s",
                    _plugin.__class__.__name__, _e,
                )

    logger.info("[Neo] Initializing FundiBrain...")
    try:
        brain = init_brain(plugins, llm, agent_core)
    except Exception as e:
        logger.error("[Neo] Brain init failed:")
        logger.error(e)
        traceback.print_exc()
        sys.exit(1)

    if not hasattr(brain, "respond") or not callable(getattr(brain, "respond")):
        logger.error("[CRITICAL] FundiBrain has no 'respond' method.")
        sys.exit(1)

    logger.info("FundiBrain is ready.")

    # ═══ INIT NEO MODEL MANAGER (NEW) ═══
    if NEO_MM_AVAILABLE:
        try:
            mm = get_model_manager()
            mm.print_active_models()
            stats = mm.get_stats()
            print(f"[Neo] Total catalog: {stats['total_catalog']}, Active: {stats['active_models']}")
        except Exception as e:
            logger.warning(f"[Neo] Model manager init: {e}")

    api_server = NeoAPIServer(brain, agent_core, llm)
    api_started = api_server.start()

    if MODE_SERVER:
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    NEO AI API SERVER ONLY                    ║
╠══════════════════════════════════════════════════════════════╣
║  Endpoint: http://{API_HOST}:{API_PORT}                          ║
║  Health:  http://{API_HOST}:{API_PORT}/api/health                ║
║  Chat:    http://{API_HOST}:{API_PORT}/api/chat                  ║
║  Hybrid:  http://{API_HOST}:{API_PORT}/hybrid                    ║
║  Vision:  http://{API_HOST}:{API_PORT}/api/vision/generate       ║
║  Images:  http://{API_HOST}:{API_PORT}/images/<file>             ║
║  UI:      http://{API_HOST}:{API_PORT}/                          ║
╚══════════════════════════════════════════════════════════════╝
""")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Neo] Server shutting down...")
        return

    if MODE_WEB:
        if api_started:
            import webbrowser
            webbrowser.open(f"http://{API_HOST}:{API_PORT}/")
            print(f"[Neo] Web UI opened: http://{API_HOST}:{API_PORT}/")
        else:
            print("[Neo] API server failed to start.")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Neo] Shutting down...")
        return

    if MODE_DESKTOP:
        if api_started:
            print("[Neo] Launching desktop app...")
            launch_desktop(f"http://{API_HOST}:{API_PORT}/")
        else:
            print("[Neo] API server failed to start.")
        return

    # ─── CLI MODE ───
    print("\n" + "=" * 60)
    print("  NEO PERSONAL INTELLIGENCE SYSTEM")
    print("  Truth Engine V8 + Agent Orchestration + Hybrid Merger")
    print("=" * 60)
    print("[Neo] STABLE CORE ONLINE")
    print("[Neo] JARVIS-CLASS AGENT ACTIVE")
    print("[Neo] TRUTH ENGINE V8 ACTIVE")
    print("[Neo] AGENT ORCHESTRATION: ENABLED")
    print("[Neo] PERSONAL INTELLIGENCE MODE: ENABLED")
    print("[Neo] MULTIMODAL VISION: ENABLED")
    if NEO_MM_AVAILABLE:
        print("[Neo] HYBRID MERGER: ENABLED")
        print("[Neo] CLOUD MODEL CATALOG: 2,249 models")
    if api_started:
        print(f"[Neo] WEB UI: http://{API_HOST}:{API_PORT}/")
        if NEO_MM_AVAILABLE:
            print(f"[Neo] HYBRID PANEL: http://{API_HOST}:{API_PORT}/hybrid")
    print()

    commands = [
        "- debug", "- show context", "- clear context", "- list goals",
        "- goal <task>", "- run goals", "- start auto", "- stop auto",
        "- personality <friendly|professional|strict|mentor|analyst|creative>",
        "- agent <query>", "- research <topic>",
        "- hybrid <prompt> [strategy=synthesis] [pool=5] [purpose=chat]",
        "- models", "- providers",
        "- generate <prompt> [width] [height] [backend=<name>]",
        "- describe <image_path>",
        "- scan", "- stats", "- exit"
    ]
    print("Commands:")
    for cmd in commands:
        print(f"  {cmd}")
    print()

    _OUTPUT_PREFIXES = (
        "[neo]", "[vision]", "[launcher]", "[debug]", "[fundibrain]",
        "[orchestrator]", "[llm]", "[api]", "[persistentfaiss]",
        "[neo] agent", "[neo] personality", "[neo] generating", "[neo] forcing",
        "[vision] image generated", "[vision] file found", "[vision error]",
        "yes, this", "the better answer is", "to fix this:", "for example:",
        "batches:", "log (voskapi:", "=", "---", "╚", "╔", "║", "╠",
    )

    while True:
        try:
            user_input = input("> ").lstrip(">").strip()
            if not user_input:
                continue
            low = user_input.lower()
            if any(low.startswith(p) for p in _OUTPUT_PREFIXES):
                continue
            if "[neo]" in low or "[vision]" in low or "[launcher]" in low or "batches:" in low:
                continue

            # Direct prefix dispatch — runs before everything else
            try:
                _prefix_res = _dispatch_prefix(user_input, agent_core)
                if _prefix_res is not None:
                    print(_prefix_res, flush=True)
                    continue
            except Exception as _e:
                print(f"[prefix] {type(_e).__name__}: {_e}", flush=True)
                continue

            cmd_lower = user_input.lower()
            if cmd_lower == "exit":
                try:
                    if hasattr(brain, "stop_autonomous"):
                        brain.stop_autonomous()
                except Exception:
                    pass
                if agent_core and "vector_store" in agent_core:
                    try:
                        agent_core["vector_store"].save()
                    except Exception:
                        pass
                print("Shutting down core engine matrices safely.")
                break

            if cmd_lower == "stats":
                stats = brain.get_stats()
                print("\n" + "-" * 40)
                print("  NEO SYSTEM STATS")
                print("-" * 40)
                print(f"  Tool Independence:     {stats.get('tool_independence', 0):.1%}")
                print(f"  Total Calls:           {stats.get('total_calls', 0)}")
                print(f"  Agent Calls:           {stats.get('agent_calls', 0)}")
                print(f"  Cognitive-Only Calls:  {stats.get('cognitive_only_calls', 0)}")
                print(f"  Tool-Assisted Calls:   {stats.get('tool_assisted_calls', 0)}")
                if agent_core and "orchestrator" in agent_core:
                    orch_stats = agent_core["orchestrator"].get_stats()
                    print(f"  Tools in Catalog:      {orch_stats.get('tools_available', 0)}")
                    print(f"  Reasoning Router:      {'Active' if orch_stats.get('reasoning_router_active') else 'Offline'}")
                print("-" * 40)
                continue

            if cmd_lower == "scan":
                print("\n[Neo] Running system scan...")
                try:
                    from core.system_scanner import NeoSystemScanner
                    scanner = NeoSystemScanner()
                    scanner.run_full_scan()
                    scanner.print_report()
                except ImportError:
                    print("[Neo] system_scanner.py not found. Skipping.")
                except Exception as e:
                    print(f"[Neo] Scan error: {e}")
                continue

            # ═══ HYBRID COMMAND ═══
            if cmd_lower.startswith("hybrid "):
                if not NEO_MM_AVAILABLE:
                    print("[Neo] Hybrid merger not available. Check imports.")
                    continue
                args = user_input[7:].strip()
                strategy = "synthesis"
                pool_size = 5
                purpose = "chat"
                m = re.search(r'strategy=(\w+)', args)
                if m:
                    strategy = m.group(1)
                    args = args[:m.start()] + args[m.end():]
                m = re.search(r'pool=(\d+)', args)
                if m:
                    pool_size = int(m.group(1))
                    args = args[:m.start()] + args[m.end():]
                m = re.search(r'purpose=(\w+)', args)
                if m:
                    purpose = m.group(1)
                    args = args[:m.start()] + args[m.end():]
                prompt = args.strip()
                if not prompt:
                    print("Usage: hybrid <prompt> [strategy=synthesis] [pool=5] [purpose=chat]")
                    continue
                print(f"[Neo] Hybrid merge: strategy={strategy}, pool={pool_size}, purpose={purpose}")
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                mm = get_model_manager()
                result = loop.run_until_complete(mm.hybrid_query(
                    prompt=prompt, purpose=purpose, strategy=strategy, pool_size=pool_size
                ))
                # --- ADDED: verbose per-model diagnostics (set HYBRID_DEBUG=1 to enable) ---
                if os.getenv("HYBRID_DEBUG"):
                    md = result.get("metadata", {})
                    print(f"[Hybrid-Debug] metadata keys: {list(md.keys())}")
                    errors = md.get("errors") or {}
                    successes = md.get("successes") or {}
                    if errors:
                        print("[Hybrid-Debug] per-model errors:")
                        for k, v in errors.items():
                            print(f"    ✗ {k}: {str(v)[:220]}")
                    else:
                        print("[Hybrid-Debug] no per-model errors (all succeeded)")
                    if successes:
                        print("[Hybrid-Debug] per-model successes:")
                        for k, v in successes.items():
                            print(f"    ✓ {k}: {v}")
                # --- END ADDED ---
                print(f"\n[Hybrid] Strategy: {result['strategy']}")
                print(f"[Hybrid] Ran {result['metadata']['total_models']} models")
                print(f"[Hybrid] Success: {result['metadata']['successful']} | Failed: {result['metadata']['failed']}")
                print(f"[Hybrid] Merge latency: {result['merge_latency']:.2f}s")
                print(f"\n{'='*60}")
                print(result['merged_output'])
                print(f"{'='*60}")
                continue

            # ═══ MODELS COMMAND ═══
            if cmd_lower == "models":
                if NEO_MM_AVAILABLE:
                    mm = get_model_manager()
                    picks = mm.get_quick_picks("chat", limit=15)
                    stats = mm.get_stats()
                    print("\n" + "="*70)
                    print("  NEO CLOUD MODEL CATALOG")
                    print("="*70)
                    for m in picks:
                        print(f"  {m['provider']:15} | {m['name']:40} | {m['type']:10} | ctx={m['ctx']}")
                    print(f"\n  ... and {stats['active_models'] - len(picks)} more active models")
                    # --- FIXED: get_stats() does not always return a 'providers' key.
                    # Fall back to len() of the manager's provider list, or 'n/a'.
                    provider_count = stats.get("providers")
                    if provider_count is None:
                        try:
                            provider_count = len(mm.list_providers())
                        except Exception:
                            provider_count = "n/a"
                    print(f"  Total catalog: {stats['total_catalog']} | Providers: {provider_count}")
                    print("="*70)
                    print("\n  Hybrid strategies: synthesis | consensus | debate | ensemble | best_of_all | parallel | cascade")
                    print("  Purposes: chat | coding | reasoning | vision | image-gen | video-gen")
                else:
                    print("[Neo] Model manager not available.")
                continue

            # ═══ PROVIDERS COMMAND ═══
            if cmd_lower == "providers":
                if NEO_MM_AVAILABLE:
                    mm = get_model_manager()
                    status = mm.list_providers()
                    print("\n" + "="*60)
                    print("  PROVIDER STATUS")
                    print("="*60)
                    for s in status:
                        icon = "✅" if s["has_key"] else "❌"
                        print(f"  {icon} {s['name']:15} | tier={s['tier']:12} | key={s['key_env'] or 'none'}")
                    print("="*60)
                else:
                    print("[Neo] Model manager not available.")
                continue

            if cmd_lower == "debug":
                print("[Neo] Debug panel:")
                if llm:
                    print(f"  LLM last engine: {getattr(llm, '_last_engine', 'unknown')}")
                    print(f"  Groq key: {'SET' if getattr(llm, 'groq_key', '') else 'MISSING'}")
                    # --- FIXED: LocalLLM stores this as `openrouter_key`, not `or_key`.
                    # Check both so older/newer builds both report correctly.
                    _or = getattr(llm, 'openrouter_key', '') or getattr(llm, 'or_key', '')
                    print(f"  OpenRouter key: {'SET' if _or else 'MISSING'}")
                    print(f"  Moonshot key: {'SET' if getattr(llm, 'moon_key', '') else 'MISSING'}")
                    print(f"  Replicate key: {'SET' if getattr(llm, 'replicate_key', '') else 'MISSING'}")
                    print(f"  Ollama ready: {getattr(llm, '_ollama_ready', False)}")
                else:
                    print("  LLM: NOT INITIALIZED")
                print(f"  Plugins: {len(plugins)}")
                if NEO_MM_AVAILABLE:
                    mm = get_model_manager()
                    st = mm.get_stats()
                    print(f"  Hybrid Merger: ENABLED")
                    print(f"  Cloud Catalog: {st['total_catalog']} models, {st['active_models']} active")
                if agent_core and "orchestrator" in agent_core:
                    o = agent_core["orchestrator"]
                    print(f"  Tool catalog: {len(o.tools)}")
                    print(f"  Plugin keys: {list(getattr(o, 'plugins', {}).keys())[:5]}...")
                else:
                    print("  Tool catalog: N/A")
                continue

            if cmd_lower == "show context":
                try:
                    ctx = brain.show_context() if hasattr(brain, "show_context") else "No context method"
                    print(ctx)
                except Exception as e:
                    print(f"[Neo] Context error: {e}")
                continue

            if cmd_lower == "clear context":
                try:
                    if hasattr(brain, "clear_context"):
                        brain.clear_context()
                    print("[Neo] Context cleared.")
                except Exception as e:
                    print(f"[Neo] Clear error: {e}")
                continue

            if cmd_lower == "list goals":
                try:
                    goals = brain.list_goals() if hasattr(brain, "list_goals") else []
                    print(f"[Neo] Goals: {goals}")
                except Exception as e:
                    print(f"[Neo] Goals error: {e}")
                continue

            if cmd_lower.startswith("personality "):
                _, name = user_input.split(maxsplit=1)
                name = name.strip("<>")
                success = False
                if hasattr(brain, "personalities") and hasattr(brain.personalities, "set_personality"):
                    success = brain.personalities.set_personality(name)
                elif hasattr(brain, "set_personality"):
                    success = brain.set_personality(name)
                print(f"[Neo] Personality: {name}" if success else f"[Neo] Invalid: {name}", flush=True)
                continue

            if cmd_lower.startswith("goal "):
                task = user_input[5:].strip()
                try:
                    if hasattr(brain, "add_goal"):
                        brain.add_goal(task)
                    print(f"[Neo] Goal added: {task}")
                except Exception as e:
                    print(f"[Neo] Goal error: {e}")
                continue

            if cmd_lower.startswith("research "):
                _, query = user_input.split(maxsplit=1)
                print(f"[Neo] Researching: {query}")
                try:
                    from core.tavily_search import tavily_search
                    result = tavily_search(query, search_depth="advanced", max_results=5, include_answer=True)
                    print(result)
                except Exception as e:
                    print(f"[Neo] Research error: {e}")
                continue

            # ─── GENERATE (image or video, direct CLI) ───
            # FIXED: now routes to video_plugin.generate_video() when the
            # prompt starts with "video", "animate", or contains "video of".
            # Previously every "generate X" went to vision.generate() and
            # "generate video of a cat" produced a still image.
            if cmd_lower.startswith("generate "):
                prompt = user_input[9:].strip()
                if not prompt:
                    print("[Neo] Usage: generate <prompt> [width] [height] [backend=<name>]")
                    continue
                backend = None
                if "backend=" in prompt.lower():
                    m = re.search(r'backend=(\w+)', prompt, re.IGNORECASE)
                    if m:
                        backend = m.group(1).lower()
                        prompt = re.sub(r'\s*backend=\w+\s*', ' ', prompt, flags=re.IGNORECASE).strip()
                parts = prompt.split()
                width, height = 1024, 768
                if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
                    width, height = int(parts[-2]), int(parts[-1])
                    prompt = " ".join(parts[:-2])
                elif len(parts) >= 2 and parts[-1].isdigit():
                    width = height = int(parts[-1])
                    prompt = " ".join(parts[:-1])

                orch = agent_core.get("orchestrator") if agent_core else None
                is_video = (
                    prompt.lower().startswith(("video ", "animate "))
                    or "video of" in prompt.lower()
                )

                if is_video:
                    video = getattr(orch, "plugins", {}).get("video_plugin") if orch else None
                    if not video:
                        try:
                            from core.plugins.video_plugin import Plugin as VVP
                            video = VVP()
                        except Exception as e:
                            print(f"[Neo] Video plugin not available: {e}")
                            continue
                    vprompt = prompt
                    for p in ("video of ", "video ", "animate "):
                        if vprompt.lower().startswith(p):
                            vprompt = vprompt[len(p):]
                            break
                    print(f"[Neo] Generating video: '{vprompt}'...", flush=True)
                    # generate() shim added to video_plugin maps to generate_video()
                    result = video.generate(vprompt, width=width, height=height, model_hint=backend)
                    print(result)
                    continue

                # Image path
                print(f"[Neo] Generating image: '{prompt}' ({width}x{height})...", flush=True)
                if backend:
                    print(f"[Neo] Forcing backend: {backend}", flush=True)
                vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
                if not vision:
                    try:
                        from core.plugins.vision_plugin import Plugin as VP
                        vision = VP()
                    except Exception as e:
                        print(f"[Neo] Vision plugin not available: {e}")
                        continue
                result = vision.generate(prompt, width, height, model_hint=backend)
                print(result)
                continue

            # ─── DESCRIBE (direct CLI) ───
            if cmd_lower.startswith("describe "):
                path = user_input[9:].strip()
                if not path:
                    print("[Neo] Usage: describe <image_path>")
                    continue
                orch = agent_core.get("orchestrator") if agent_core else None
                vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
                if not vision:
                    try:
                        from core.plugins.vision_plugin import Plugin as VP
                        vision = VP()
                    except Exception as e:
                        print(f"[Neo] Vision plugin not available: {e}")
                        continue
                result = vision.describe(path)
                print(result, flush=True)
                continue

            # ─── AGENT (with skill pre-flight, image fast path, then ReAct) ───
            # FIXED: routes agent queries through NeoBrain's skill pre-flight
            # BEFORE the orchestrator. "agent translate hello to swahili" now
            # hits the translate skill directly instead of the LLM.
            if cmd_lower.startswith("agent "):
                query = user_input[6:].strip()
                agent_lower = query.lower()

                # Image fast path (unchanged)
                image_prefixes = ["draw ", "paint ", "sketch ", "generate an image", "generate a picture", "create an image", "create a picture", "make an image", "make a picture", "image of ", "picture of "]
                if any(agent_lower.startswith(p) for p in image_prefixes):
                    orch = agent_core.get("orchestrator") if agent_core else None
                    vision = getattr(orch, "plugins", {}).get("vision_plugin") if orch else None
                    if not vision:
                        try:
                            from core.plugins.vision_plugin import Plugin as VP
                            vision = VP()
                        except Exception as e:
                            print(f"[Neo] Vision plugin not available: {e}")
                            continue
                    prompt = query
                    for prefix in image_prefixes:
                        if prompt.lower().startswith(prefix):
                            prompt = prompt[len(prefix):]
                            break
                    print(f"[Neo] Agent generating image: '{prompt.strip()}'...", flush=True)
                    result = vision.generate(prompt.strip())
                    print(result, flush=True)
                    continue

                # --- NEW: Skill pre-flight for agent queries ---
                if agent_core and "orchestrator" in agent_core:
                    try:
                        from core.services.neo_brain import _try_skill_pre_flight, _is_personal_query
                        if not _is_personal_query(query):
                            skill_result = _try_skill_pre_flight(query, agent_core["orchestrator"])
                            if skill_result is not None:
                                print(f"[Neo] Skill pre-flight (agent): {query!r}")
                                print(skill_result, flush=True)
                                continue
                    except Exception as e:
                        print(f"[Neo] Agent skill pre-flight error: {e}")

                # --- Fall through to ReAct orchestrator ---
                if not agent_core or "orchestrator" not in agent_core:
                    print("[Neo] Agent core not initialized. Using standard mode.")
                    engine_output = asyncio.run(brain.respond(query))
                else:
                    print("[Neo] Agent mode engaged...")
                    engine_output = asyncio.run(agent_core["orchestrator"].run(query, getattr(brain, "conversation_history", [])))
                    if os.getenv("NEO_DEBUG"):
                        trace = agent_core["orchestrator"].get_execution_log()
                        print(f"\n[Debug] Agent trace ({len(trace)} steps):")
                        for step in trace:
                            print(f"  {step.get('state', '?')}: {step.get('action', step.get('tool', 'response'))}")
                print(engine_output)
                continue

            # Plugin pre-flight (CLI)
            _plugin_pre = _try_plugin_preflight(user_input, agent_core)
            if _plugin_pre:
                print(_plugin_pre)
                continue

            # /verify and /fast go straight to brain.respond()
            _ul = user_input.strip().lower()
            if _ul.startswith("/verify ") or _ul.startswith("/fast "):
                engine_output = asyncio.run(brain.respond(user_input))
                print(engine_output, flush=True)
                continue

            # FAST PATH: Factual queries
            # Agents pre-flight (CLI)
            _agents_pre = _try_agents_preflight(user_input, agent_core)
            if _agents_pre:
                print(_agents_pre)
                continue

            factual_answer = _handle_factual_query(user_input, agent_core)
            if factual_answer:
                print(f"\n📚 {factual_answer}\n")
                continue

            # Standard chat
            engine_output = asyncio.run(brain.respond(user_input))
            print(engine_output, flush=True)

        except (KeyboardInterrupt, EOFError):
            print("\n\nBreak sequence processed. Exiting system safely.")
            break
        except Exception as e:
            logger.error("[FundiBrain Error] " + str(e))
            traceback.print_exc()

if __name__ == "__main__":
    main()