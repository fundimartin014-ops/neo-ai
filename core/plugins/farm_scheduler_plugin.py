"""farm_scheduler_plugin.py — daily farm brief, driven by Neo's own runtime.

Flow:
  - On startup: plugin arms itself (prints config).
  - After agent_core is ready: launcher calls on_agent_core(), which starts
    a background thread.
  - Every N seconds the thread checks: is it past the scheduled time today
    and we haven't fired? If so, invoke the `agents` skill with
    "farm: <location>", save the markdown to sandbox/digests/, and notify
    via agents.notifiers (Discord + Slack + WhatsApp + email).

Config (env):
  FARM_BRIEF_ENABLED=true       (default true)
  FARM_BRIEF_TIME=06:00         (HH:MM, local time)
  FARM_BRIEF_LOCATION=Nakuru
  FARM_BRIEF_CHECK_SECONDS=60
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("farm_scheduler_plugin")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_PATH = PROJECT_ROOT / "data" / "farm_scheduler_state.json"
OUTPUT_DIR = PROJECT_ROOT / "sandbox" / "digests"


def _env_flag(name: str, default: bool = True) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


class Plugin:
    """Daily farm brief, routed through Neo's own agents runtime."""

    def __init__(self):
        self.enabled = _env_flag("FARM_BRIEF_ENABLED", True)
        self.schedule_time = (os.getenv("FARM_BRIEF_TIME") or "06:00").strip()
        self.location = (os.getenv("FARM_BRIEF_LOCATION") or "Nakuru").strip()
        self.check_interval = int(os.getenv("FARM_BRIEF_CHECK_SECONDS") or "60")
        self.agent_core = None
        self._thread = None
        self._stop = threading.Event()

    # ---------------------------------------------------------------- startup
    def run(self) -> None:
        if not self.enabled:
            logger.info("[FarmScheduler] disabled (FARM_BRIEF_ENABLED=false)")
            return
        logger.info(
            "[FarmScheduler] armed — daily %s for %s",
            self.schedule_time, self.location,
        )

    def on_agent_core(self, agent_core) -> None:
        """Called by launcher after agent_core is initialized."""
        if not self.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self.agent_core = agent_core
        self._thread = threading.Thread(
            target=self._loop, name="FarmScheduler", daemon=True
        )
        self._thread.start()
        logger.info("[FarmScheduler] scheduler thread started")

    # ------------------------------------------------------------------ loop
    def _loop(self) -> None:
        time.sleep(20)  # let the agents skill warm up
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception("[FarmScheduler] tick failed: %s", e)
            self._stop.wait(self.check_interval)

    def _tick(self) -> None:
        now = datetime.now()
        target = self._parse_time(self.schedule_time)
        if target is None:
            return
        if (now.hour, now.minute) < target:
            return
        today = now.strftime("%Y-%m-%d")
        state = self._load_state()
        if state.get("last_run_date") == today:
            return

        logger.info("[FarmScheduler] firing daily brief for %s", self.location)
        text = self._run_brief()
        if text is None:
            logger.warning("[FarmScheduler] brief failed; retry on next tick")
            return
        self._save_state({"last_run_date": today, "last_len": len(text)})
        logger.info("[FarmScheduler] brief complete (%d chars)", len(text))

    # ------------------------------------------------------------- execution
    def _run_brief(self):
        orch = (self.agent_core or {}).get("orchestrator")
        if not orch:
            logger.warning("[FarmScheduler] no orchestrator available")
            return None
        tool = None
        plugins = getattr(orch, "plugins", {}) or {}
        for key in ("agents", "agents_skill", "agent"):
            if key in plugins:
                tool = plugins[key]
                break
        if tool is None:
            logger.warning("[FarmScheduler] agents tool not in registry")
            return None

        query = f"farm: {self.location}"
        try:
            text = tool(query=query)
        except Exception as e:
            logger.exception("[FarmScheduler] tool call failed: %s", e)
            return None
        text = str(text or "").strip()
        if not text or text.startswith("[Tool error"):
            logger.warning("[FarmScheduler] empty or error response")
            return None

        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            out = OUTPUT_DIR / f"farm-{datetime.now().strftime('%Y-%m-%d')}.md"
            out.write_text(text, encoding="utf-8")
            logger.info("[FarmScheduler] wrote %s", out)
        except Exception as e:
            logger.warning("[FarmScheduler] save failed: %s", e)

        self._notify(text)
        return text

    def _notify(self, text: str) -> None:
        try:
            import asyncio
            from agents.notifiers import notify_brief
            title = f"Farm brief — {self.location} — {datetime.now().strftime('%Y-%m-%d')}"
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(
                            asyncio.run, notify_brief(title, text)
                        ).result(timeout=20)
                else:
                    loop.run_until_complete(notify_brief(title, text))
            except RuntimeError:
                asyncio.run(notify_brief(title, text))
        except Exception as e:
            logger.warning("[FarmScheduler] notify failed: %s", e)

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _parse_time(s):
        try:
            h, m = s.split(":", 1)
            h, m = int(h), int(m)
            if 0 <= h < 24 and 0 <= m < 60:
                return (h, m)
        except Exception:
            pass
        return None

    def _load_state(self):
        try:
            if STATE_PATH.exists():
                return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_state(self, state):
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
        except Exception as e:
            logger.warning("[FarmScheduler] state save failed: %s", e)

    def stop(self):
        self._stop.set()
