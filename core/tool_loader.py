"""
core/tool_loader.py

Lazy discovery + registration of skills, agents, and core modules as
orchestrator tools.

Design:
    - Boot cost is near-zero. Modules are NOT imported at registration.
    - Each tool is a `LazyTool` stub. On first call, it imports + instantiates.
    - Supports class-based (MathSkill.process) AND function-based (run) modules.
    - All failures are logged, never raised. One broken module can't block boot.
    - Registration is deterministic; name collisions get a kind prefix.
"""

import ast
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Where the source lives. Overridden by register_lazy_tools() caller.
PROJECT_ROOT: Optional[Path] = None

# ---- Method/function name candidates, in priority order ----
CLASS_METHODS = ["process", "run", "execute", "handle", "apply", "respond", "query"]
FUNC_METHODS = ["run", "process", "execute", "handle", "route", "search", "reason", "engine", "query", "main"]

# ---- Core modules that are safe + useful to expose lazily ----
# NOTE: this list is only core/ files. skills/, agents/, knowledge/,
# reasoning/, neofarm/ are discovered automatically by directory scan.
CORE_ALLOWLIST = [
    # reasoning / cognitive
    "truth_engine", "source_ranker", "critic", "deep_thinker",
    "belief_system", "consensus_trace", "debate_engine", "parallel_tools",
    "unified_search", "web_fallback", "self_reflection", "self_evaluator",
    "reflection_engine", "proactive_agent", "quality_monitor", "rl_feedback",
    "tool_learning", "goals",
    # knowledge
    "knowledge_builder", "knowledge_engine", "knowledge_extractor",
    "knowledge_graph", "entity_graph", "semantic_extractor",
    # memory
    "embedding_memory", "semantic_memory", "working_memory",
    "context_memory", "governed_memory", "memory_utils",
    # self-improvement / autonomous (test carefully, but they're wired)
    "self_improvement", "autonomous_agent", "autonomous_engine",
    "autonomous_loop", "background_loop", "agent_loop", "react_loop",
    "agent_engine", "agent_executor", "agent_planner",
    # utilities
    "code_validator", "url_learner", "tts", "vision_ollama",
    "voice_input", "wake_word", "system_control", "device_controller",
    "device_intents", "telemetry", "session", "messaging",
    "github_client", "notifier", "utils",
]


class LazyTool:
    """A callable tool that imports + instantiates its target on first call."""

    __slots__ = ("name", "spec", "_callable", "_instance", "_loaded", "_load_error")

    def __init__(self, name: str, spec: Dict[str, Any]):
        self.name = name
        self.spec = spec
        self._callable = None
        self._instance = None
        self._loaded = False
        self._load_error = None

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return self._callable is not None
        self._loaded = True
        try:
            mod = importlib.import_module(self.spec["module_path"])
            cls_name = self.spec.get("class_name")
            method = self.spec["method_name"]
            if cls_name:
                cls = getattr(mod, cls_name)
                self._instance = cls()
                self._callable = getattr(self._instance, method)
            else:
                self._callable = getattr(mod, method)
            logger.info(
                f"[ToolLoader] Loaded {self.name} "
                f"({self.spec['module_path']}.{cls_name or method})"
            )
            return True
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"[ToolLoader] {self.name} failed to load: {e}")
            return False

    def _invoke(self, kwargs: Dict[str, Any]) -> Any:
        """Try kwargs → dict → single string, in that order."""
        # 1) explicit kwargs
        try:
            return self._callable(**kwargs)
        except TypeError:
            pass
        # 2) whole params dict
        try:
            return self._callable(kwargs)
        except TypeError:
            pass
        # 3) first value or joined string
        if kwargs:
            first = next(iter(kwargs.values()))
            if isinstance(first, str):
                try:
                    return self._callable(first)
                except TypeError:
                    pass
            try:
                return self._callable(" ".join(str(v) for v in kwargs.values()))
            except TypeError:
                pass
        # 4) no-arg call
        try:
            return self._callable()
        except TypeError:
            raise

    def __call__(self, **kwargs) -> Any:
        if not self._ensure_loaded():
            return f"[Tool error] {self.name}: {self._load_error}"

        # Run: support both sync and async
        try:
            result = self._invoke(kwargs)
        except Exception as e:
            return f"[Tool error] {self.name}: {e}"

        # Unwrap common shapes: {"result": x} or {"error": y}
        if isinstance(result, dict):
            if "error" in result:
                return f"[Tool error] {self.name}: {result['error']}"
            if "result" in result:
                result = result["result"]

        # Await coroutines
        try:
            import asyncio, inspect
            if inspect.iscoroutine(result):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            result = pool.submit(lambda: asyncio.run(result)).result()
                    else:
                        result = loop.run_until_complete(result)
                except RuntimeError:
                    result = asyncio.run(result)
        except Exception:
            pass

        return result

    def __repr__(self):
        return f"<LazyTool {self.name} spec={self.spec['module_path']}>"


# ---------------------------------------------------------------------------
# AST inspection — discover callables without importing
# ---------------------------------------------------------------------------

def _find_method(class_node: ast.ClassDef, candidates: List[str]) -> Optional[str]:
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in candidates:
            return item.name
    return None


def _find_function(tree: ast.Module, candidates: List[str]) -> Optional[str]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in candidates:
            return node.name
    return None


def _inspect_file(path: Path, kind: str, module_prefix: str) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return specs

    module_path = f"{module_prefix}.{path.stem}"
    base_name = path.stem.replace("_skill", "").replace("_agent", "").replace("_plugin", "").rstrip("_")

    # Class-based discovery
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if kind == "skill" and node.name.endswith("Skill"):
            method = _find_method(node, CLASS_METHODS)
            if method:
                specs.append({
                    "name": base_name,
                    "kind": kind,
                    "module_path": module_path,
                    "class_name": node.name,
                    "method_name": method,
                })
        elif kind == "agent" and node.name.endswith("Agent") and node.name != "BaseAgent":
            method = _find_method(node, CLASS_METHODS)
            if method:
                specs.append({
                    "name": base_name,
                    "kind": kind,
                    "module_path": module_path,
                    "class_name": node.name,
                    "method_name": method,
                })

    # Function-based fallback (only if no class matched)
    if not specs:
        fn = _find_function(tree, FUNC_METHODS)
        if fn:
            specs.append({
                "name": base_name,
                "kind": kind,
                "module_path": module_path,
                "class_name": None,
                "method_name": fn,
            })

    return specs


# ---------------------------------------------------------------------------
# Directory scans
# ---------------------------------------------------------------------------

def _scan_dir(root: Path, dirname: str, kind: str, skip: tuple = ()) -> List[Dict[str, Any]]:
    specs = []
    d = root / dirname
    if not d.exists():
        return specs
    for f in sorted(d.glob("*.py")):
        if f.stem.startswith("_") or f.stem in skip:
            continue
        specs.extend(_inspect_file(f, kind, dirname))
    return specs


def discover_all(project_root: Path) -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []

    # Discovered by convention
    specs.extend(_scan_dir(project_root, "skills", "skill"))
    specs.extend(_scan_dir(project_root, "agents", "agent",
                           skip=("base_agent", "task_queue")))
    specs.extend(_scan_dir(project_root, "knowledge", "knowledge",
                           skip=("__init__",)))
    specs.extend(_scan_dir(project_root, "reasoning", "reasoning",
                           skip=("__init__",)))
    specs.extend(_scan_dir(project_root, "neofarm", "neofarm",
                           skip=("__init__", "demo_farmer")))

    # Core allowlist
    core = project_root / "core"
    for mod_name in CORE_ALLOWLIST:
        f = core / f"{mod_name}.py"
        if f.exists():
            specs.extend(_inspect_file(f, "core", "core"))

    return specs


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def register_lazy_tools(orchestrator, project_root: Path) -> Dict[str, int]:
    """
    Register every discoverable callable as a lazy tool on the orchestrator.
    Returns {"registered": N, "skipped": M, "collisions": K}.
    """
    global PROJECT_ROOT
    PROJECT_ROOT = project_root

    specs = discover_all(project_root)
    used_names = set(orchestrator.plugins.keys())  # existing plugin names
    registered = 0
    skipped = 0
    collisions = 0

    # Sort so agents/skills register before generic core names (agent_planner over planner)
    kind_priority = {"skill": 0, "agent": 1, "knowledge": 2, "reasoning": 3,
                     "neofarm": 4, "core": 5}
    specs.sort(key=lambda s: (kind_priority.get(s["kind"], 9), s["name"]))

    for spec in specs:
        name = spec["name"]
        if name in used_names:
            # Disambiguate with kind prefix
            name = f"{spec['kind']}_{name}"
            collisions += 1
        if name in used_names:
            skipped += 1
            continue

        tool = LazyTool(name, spec)
        orchestrator.plugins[name] = tool
        used_names.add(name)
        registered += 1

        # Also add to the tool catalog so the LLM knows about it
        orchestrator.tools.append({
            "name": name,
            "description": f"{spec['kind']} tool from {spec['module_path']}",
            "parameters": {
                "query": {"type": "string", "optional": True},
                "expression": {"type": "string", "optional": True},
                "inputs": {"type": "object", "optional": True},
            },
        })

    logger.info(
        f"[ToolLoader] Registered {registered} lazy tools "
        f"({collisions} collisions renamed, {skipped} skipped)."
    )
    return {"registered": registered, "skipped": skipped, "collisions": collisions}