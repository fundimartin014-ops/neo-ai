"""Background loop that runs due scheduled jobs.

Handles:
- {{today}}, {{yesterday}}, {{tomorrow}}, {{now}}, {{timestamp}} in goals
- Discord notification after each run (if DISCORD_WEBHOOK_URL is set)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


# ---------------------------------------------------------------------------
# Date placeholders
# ---------------------------------------------------------------------------
_DATE_KEYS = {
    "today":     lambda n: n.strftime("%Y-%m-%d"),
    "yesterday": lambda n: (n - timedelta(days=1)).strftime("%Y-%m-%d"),
    "tomorrow":  lambda n: (n + timedelta(days=1)).strftime("%Y-%m-%d"),
    "now":       lambda n: n.strftime("%Y-%m-%d_%H-%M-%S"),
    "timestamp": lambda n: str(int(n.timestamp())),
    "iso":       lambda n: n.isoformat(),
}


def expand_dates(text: str, now: datetime | None = None) -> str:
    """Replace {{today}}/{{yesterday}}/{{now}}/etc. with actual values."""
    now = now or datetime.now()
    def repl(m):
        key = m.group(1).strip().lower()
        fn = _DATE_KEYS.get(key)
        return fn(now) if fn else m.group(0)
    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", repl, text)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
async def _notify_job(job: dict, result: dict | None, error: str | None = None) -> None:
    from agents.notifiers import notify_brief

    name = job.get("name", "?")
    if error:
        text = f"❌ Job **{name}** failed:\n```\n{error[:400]}\n```"
    else:
        plan = (result or {}).get("plan") or []
        preview = ""
        for r in reversed((result or {}).get("results") or []):
            prev = str(r.get("result", "")).strip()
            if prev:
                preview = prev[:500]
                break
        text = (
            f"✅ Job **{name}** completed — {len(plan)} step(s)\n"
            f"Goal: {job.get('goal', '')[:180]}\n"
            f"```\n{preview}\n```"
        )
    try:
        await notify_brief(name, text)
    except Exception as exc:
        logger.warning("notify failed: %s", exc)


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------
async def _run_goal(registry, goal: str) -> dict:
    goal = expand_dates(goal)

    plan_raw = await registry.acommand("PlannerAgent", "plan", goal)
    if isinstance(plan_raw, str):
        try:
            plan_data = json.loads(plan_raw)
        except Exception:
            plan_data = {"steps": [goal]}
    else:
        plan_data = plan_raw or {}
    steps = plan_data.get("steps") or [goal]

    executor = registry.get("ExecutorAgent")
    if executor is None:
        return {"goal": goal, "error": "ExecutorAgent not registered"}

    raw_results = executor.run(steps, goal=goal)

    memory = registry.get("MemoryAgent")
    if memory is not None:
        try:
            await memory.arun(raw_results)
        except Exception:
            pass

    return {
        "goal": goal,
        "plan": steps,
        "results": [{"step": s, "result": r} for s, r in raw_results],
    }


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------
async def run_due_jobs(registry) -> int:
    scheduler = registry.get("SchedulerAgent")
    if not scheduler:
        return 0

    jobs = await scheduler.due_jobs()
    if not jobs:
        return 0

    count = 0
    for job in jobs:
        logger.info("firing job '%s' (id=%s): %s", job["name"], job["id"], job["goal"])
        error = None
        result = None
        try:
            result = await _run_goal(registry, job["goal"])
            summary = json.dumps(result, default=str)[:400]
        except Exception as exc:
            error = str(exc)
            summary = f"error: {exc}"
            logger.exception("job %s failed", job["id"])
        try:
            await scheduler.mark_run(job["id"], summary, job["schedule"])
        except Exception as exc:
            logger.exception("mark_run failed for job %s: %s", job["id"], exc)

        await _notify_job(job, result, error)
        count += 1
    return count


async def scheduler_loop(registry, interval: int = 15) -> None:
    logger.info("Scheduler loop started (interval=%ss)", interval)
    while True:
        try:
            n = await run_due_jobs(registry)
            if n:
                logger.info("scheduler fired %d job(s)", n)
        except asyncio.CancelledError:
            logger.info("scheduler cancelled")
            raise
        except Exception as exc:
            logger.exception("scheduler tick failed: %s", exc)
        await asyncio.sleep(interval)


def start_worker(registry, interval: int = 15) -> asyncio.Task:
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        return _worker_task
    _worker_task = asyncio.create_task(scheduler_loop(registry, interval=interval))
    return _worker_task


async def stop_worker() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except (asyncio.CancelledError, Exception):
        pass
    _worker_task = None
