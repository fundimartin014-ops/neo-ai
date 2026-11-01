"""agents_skill.py — exposes the multi-agent runtime to Neo's orchestrator."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

logger = logging.getLogger("agents_skill")

from agents.profiles import active_profile, is_allowed, describe as describe_profile


ALIASES = {
    "search":       "SearchAgent",
    "summarize":    "SummarizerAgent",
    "summary":      "SummarizerAgent",
    "farm":         "FarmerDigestAgent",
    "disease":      "DiseaseAlertAgent",
    "image_analysis": "ImageAnalysisAgent",
    "transcribe":     "TranscriptionAgent",
    "location":       "LocationAgent",
    "speak":          "SpeechAgent",
    "device":         "DeviceControlAgent",
    "iot":            "DeviceControlAgent",
    "tts":            "SpeechAgent",
    "voice":          "TranscriptionAgent",
    "analyze_image": "ImageAnalysisAgent",
    "diagnose":     "DiseaseAlertAgent",
    "brief":        "FarmerDigestAgent",
    "web":          "WebAgent",
    "fetch":        "WebAgent",
    "open":         "WebAgent",
    "file":         "FileManagementAgent",
    "files":        "FileManagementAgent",
    "system":       "SystemAgent",
    "shell":        "SystemAgent",
    "knowledge":    "KnowledgeAgent",
    "sentiment":    "SentimentAgent",
    "validate":     "InputValidationAgent",
    "scheduler":    "SchedulerAgent",
    "schedule":     "SchedulerAgent",
    "market":       "MarketAgent",
    "notify":       "NotificationAgent",
    "notification": "NotificationAgent",
    "tag":          "TaggingAgent",
    "tagging":      "TaggingAgent",
    "task":         "TaskAgent",
    "profile":      "UserProfileAgent",
    "memory":       "MemoryAgent",
}


class AgentsSkill:
    name = "agents"

    def __init__(self):
        self._registry = None
        self._loop = None
        self._thread = None
        self._ready = threading.Event()
        self._boot_lock = threading.Lock()
        self._stopped = False

    # ------------------------------------------------------------------ boot
    def _ensure_booted(self, timeout: float = 90.0) -> bool:
        if self._registry is not None:
            return True
        with self._boot_lock:
            if self._registry is not None:
                return True
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._boot, name="AgentsSkillLoop", daemon=True
                )
                self._thread.start()
        ok = self._ready.wait(timeout=timeout)
        if not ok:
            logger.error("[agents_skill] boot timed out")
        return ok

    def _boot(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._registry = self._loop.run_until_complete(self._build())
            logger.info(
                "[agents_skill] registry ready: %d agents",
                len(self._registry.all()),
            )
        except Exception as e:
            logger.exception("[agents_skill] boot failed: %s", e)
            self._registry = None
            self._ready.set()
            return

        # Signal ready NOW that the registry exists
        self._ready.set()

        # CRITICAL: keep the loop running so subsequent coroutines
        # submitted with run_coroutine_threadsafe actually execute.
        try:
            self._loop.run_forever()
        except Exception as e:
            logger.exception("[agents_skill] loop crashed: %s", e)

    async def _build(self):
        from agents.config import Config
        from agents.persistence import Database
        from agents.message_bus import MessageBus
        from agents.api_server import build_registry

        Config.ensure_dirs()
        db = Database(Config.DB_PATH)
        await db.connect()
        bus = MessageBus()
        reg = build_registry(bus=bus, db=db)

        for name in ("ExecutorAgent", "CriticAgent", "MemoryAgent"):
            agent = reg.get(name)
            if agent and hasattr(agent, "start"):
                try:
                    agent.start()
                except Exception:
                    pass
        return reg

    # ------------------------------------------------------------------ submit
    def _submit(self, coro, timeout: float = 120.0):
        if self._loop is None or self._registry is None:
            raise RuntimeError("agents_skill not ready")
        if self._loop.is_closed():
            raise RuntimeError("agents_skill loop is closed")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    # ------------------------------------------------------------------ process
    def profile_info(self) -> str:
        return describe_profile()

    def process(self, query: Any = None, expression: Any = None,
                inputs: Any = None, text: Any = None, **kw: Any) -> str:
        # Boot the registry on ANY call (including empty query for warmup)
        if not self._ensure_booted():
            return "agents_skill: startup timed out"
        q = self._pick_query(query, expression, inputs, text, kw)
        if not q:
            return (
                "agents_skill ready. Try 'search: kenya news', "
                "'farm: Nakuru', or a free-form goal."
            )
        return self._dispatch(q)

    def run(self, query: Any = None, **kw: Any) -> str:
        return self.process(query=query, **kw)

    def handle(self, query: Any = None, **kw: Any) -> str:
        return self.process(query=query, **kw)

    def execute(self, query: Any = None, **kw: Any) -> str:
        return self.process(query=query, **kw)

    def query(self, query: Any = None, **kw: Any) -> str:
        return self.process(query=query, **kw)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _pick_query(query, expression, inputs, text, kw) -> str:
        for cand in (query, expression, text):
            if isinstance(cand, str) and cand.strip():
                return cand.strip()
        if isinstance(inputs, str) and inputs.strip():
            return inputs.strip()
        if isinstance(inputs, dict):
            for key in ("query", "text", "goal", "input", "command"):
                v = inputs.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        for v in kw.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    # ------------------------------------------------------------------ dispatch
    def _dispatch(self, text: str) -> str:
        if not self._ensure_booted():
            return "agents_skill: startup timed out"

        if ":" in text:
            head, _, tail = text.partition(":")
            head_l = head.strip().lower()
            if head_l in ALIASES:
                if not is_allowed(head_l):
                    from agents.profiles import allowed_aliases
                    allowed = allowed_aliases() or set()
                    allowed_str = ", ".join(sorted(allowed)) if allowed else "(all)"
                    return (
                        f"agents_skill: alias '{head_l}' is disabled in the "
                        f"current profile '{active_profile()}'."
                        f"\nAvailable aliases: {allowed_str}"
                        f"\nTo enable '{head_l}', either switch profiles "
                        f"(set env NEO_AGENT_PROFILE or edit config/agent_profiles.json) "
                        f"or add '{head_l}' to the profile's agents list."
                    )
                agent_name = ALIASES[head_l]
                agent = self._registry.get(agent_name)
                if agent is None:
                    return f"agents_skill: '{agent_name}' not registered"
                payload = tail.strip()
                try:
                    return str(self._submit(agent.arun(payload)))
                except Exception as e:
                    logger.exception("[agents_skill] %s failed", agent_name)
                    return f"agents_skill error in {agent_name}: {e}"

        return self._run_pipeline(text)

    def _run_pipeline(self, goal: str) -> str:
        try:
            plan_raw = self._submit(
                self._registry.acommand("PlannerAgent", "plan", goal)
            )
        except Exception as e:
            return f"agents_skill planner error: {e}"

        if isinstance(plan_raw, str):
            try:
                plan_data = json.loads(plan_raw)
            except Exception:
                plan_data = {"steps": [goal]}
        else:
            plan_data = plan_raw or {"steps": [goal]}
        steps = plan_data.get("steps") or [goal]

        executor = self._registry.get("ExecutorAgent")
        if executor is None:
            return "agents_skill: ExecutorAgent missing"

        try:
            results = executor.run(steps, goal=goal)
        except Exception as e:
            return f"agents_skill executor error: {e}"

        memory = self._registry.get("MemoryAgent")
        if memory is not None:
            try:
                self._submit(memory.arun(results))
            except Exception:
                pass

        out = [f"PLAN ({len(steps)} step{'s' if len(steps) != 1 else ''}):"]
        for i, s in enumerate(steps, 1):
            out.append(f"  {i}. {s}")
        out.append("")
        out.append("RESULTS:")
        for step, result in results:
            out.append(f"\n[{step}]")
            out.append(str(result)[:1500])
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Module-level singletons for loaders that prefer functions over classes
# ---------------------------------------------------------------------------
_singleton: AgentsSkill | None = None


def _get() -> AgentsSkill:
    global _singleton
    if _singleton is None:
        _singleton = AgentsSkill()
    return _singleton


def run(query: Any = None, **kw: Any) -> str:
    return _get().run(query=query, **kw)


def process(query: Any = None, **kw: Any) -> str:
    return _get().process(query=query, **kw)


def handle(query: Any = None, **kw: Any) -> str:
    return _get().handle(query=query, **kw)
