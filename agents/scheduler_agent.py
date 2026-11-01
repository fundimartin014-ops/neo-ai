"""Cron-lite scheduler: store, list, delete recurring jobs in SQLite."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from agents.base_agent import BaseAgent
from agents.persistence import Database


def compute_next_run(schedule: str, now: datetime | None = None) -> datetime:
    """Parse a schedule string and return its next fire time.

    Supported formats:
      every:30s | every:5m | every:2h | every:1d
      hourly            (fires on the hour)
      daily@HH:MM       (fires every day at local time HH:MM)
    """
    now = now or datetime.now()
    s = (schedule or "").strip().lower()

    if s.startswith("every:"):
        spec = s[len("every:"):]
        m = re.match(r"^(\d+)(s|m|h|d)$", spec)
        if not m:
            raise ValueError(f"bad interval: {schedule!r}")
        n = int(m.group(1))
        unit = m.group(2)
        seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit] * n
        return now + timedelta(seconds=seconds)

    if s == "hourly":
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    if s.startswith("daily@"):
        hm = s[len("daily@"):]
        m = re.match(r"^(\d{1,2}):(\d{2})$", hm)
        if not m:
            raise ValueError(f"bad daily time: {schedule!r}")
        hour = int(m.group(1))
        minute = int(m.group(2))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError(f"bad time: {schedule!r}")
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    raise ValueError(f"unknown schedule format: {schedule!r}")


class SchedulerAgent(BaseAgent):
    name = "SchedulerAgent"
    capabilities = ("schedule",)

    def __init__(self, db: Database, **kw: Any) -> None:
        super().__init__(**kw)
        self.db = db

    async def create(self, name: str, schedule: str, goal: str) -> str:
        next_run = compute_next_run(schedule)
        now_iso = datetime.now().isoformat()
        await self.db.execute(
            "INSERT INTO scheduled_jobs (name, schedule, goal, enabled, next_run, created_at) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (name.strip(), schedule.strip(), goal.strip(),
             next_run.isoformat(), now_iso),
        )
        row = await self.db.fetchone("SELECT last_insert_rowid() AS id")
        jid = int(row["id"]) if row else -1
        return f"Created job '{name}' (id={jid}); next run {next_run.isoformat(timespec='minutes')}"

    async def list_jobs(self) -> str:
        rows = await self.db.fetchall(
            "SELECT id, name, schedule, goal, enabled, last_run, next_run "
            "FROM scheduled_jobs ORDER BY id"
        )
        if not rows:
            return "(no scheduled jobs)"
        out = []
        for r in rows:
            status = "on" if r["enabled"] else "off"
            out.append(
                f"[{r['id']}] {r['name']} ({r['schedule']}, {status})\n"
                f"    goal: {r['goal']}\n"
                f"    last: {r['last_run'] or '(never)'}  next: {r['next_run']}"
            )
        return "\n".join(out)

    async def delete(self, job_id: int) -> str:
        await self.db.execute("DELETE FROM scheduled_jobs WHERE id = ?", (int(job_id),))
        return f"Deleted job {job_id}."

    async def enable(self, job_id: int, enabled: bool = True) -> str:
        if enabled:
            row = await self.db.fetchone(
                "SELECT schedule FROM scheduled_jobs WHERE id = ?", (int(job_id),)
            )
            if not row:
                return f"No such job: {job_id}"
            next_run = compute_next_run(row["schedule"]).isoformat()
            await self.db.execute(
                "UPDATE scheduled_jobs SET enabled = 1, next_run = ? WHERE id = ?",
                (next_run, int(job_id)),
            )
        else:
            await self.db.execute(
                "UPDATE scheduled_jobs SET enabled = 0 WHERE id = ?", (int(job_id),)
            )
        return f"Job {job_id} enabled={enabled}."

    async def due_jobs(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now()
        rows = await self.db.fetchall(
            "SELECT id, name, schedule, goal, next_run FROM scheduled_jobs "
            "WHERE enabled = 1 AND next_run <= ? ORDER BY next_run",
            (now.isoformat(),),
        )
        return [dict(r) for r in rows]

    async def mark_run(self, job_id: int, result: str, schedule: str) -> None:
        next_run = compute_next_run(schedule).isoformat()
        now_iso = datetime.now().isoformat()
        await self.db.execute(
            "UPDATE scheduled_jobs SET last_run = ?, last_result = ?, next_run = ? "
            "WHERE id = ?",
            (now_iso, (result or "")[:500], next_run, int(job_id)),
        )

    async def ahandle_command(self, command: str, *args: Any) -> str:
        if command == "create":
            return await self.create(args[0], args[1], args[2])
        if command == "list":
            return await self.list_jobs()
        if command == "delete":
            return await self.delete(args[0])
        if command == "enable":
            return await self.enable(args[0], True)
        if command == "disable":
            return await self.enable(args[0], False)
        return f"SchedulerAgent - command '{command}' not implemented."

    def handle_command(self, command: str, *args: Any) -> str:
        import asyncio
        return asyncio.run(self.ahandle_command(command, *args))
