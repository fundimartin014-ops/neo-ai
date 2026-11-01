"""autonomous_test_harness.py — run every capability for N minutes.

Run:
    python autonomous_test_harness.py              # default 60 min
    python autonomous_test_harness.py --minutes 5  # quick run
    python autonomous_test_harness.py --rounds 1   # single pass

Writes:
    data/test_reports/harness_YYYY-MM-DD_HHMMSS.md
    data/test_reports/harness_YYYY-MM-DD_HHMMSS.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

REPORT_DIR = PROJECT_ROOT / "data" / "test_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Test registry
# ---------------------------------------------------------------------------
class TestCase:
    def __init__(self, name: str, category: str, fn: Callable[[], Any],
                 timeout: float = 30.0, needs_registry: bool = True):
        self.name = name
        self.category = category
        self.fn = fn
        self.timeout = timeout
        self.needs_registry = needs_registry


def _call_agent(registry, agent_name: str, command: str = "run", *args,
                timeout: float = 30.0) -> str:
    """Call an agent synchronously with a hard timeout."""
    if registry is None:
        raise RuntimeError("registry not built")
    agent = registry.get(agent_name)
    if agent is None:
        raise RuntimeError(f"agent not registered: {agent_name}")
    result: dict = {}

    def runner():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if command == "run" or command is None:
                    coro = agent.arun(*args)
                else:
                    coro = agent.ahandle_command(command, *args)
                result["value"] = loop.run_until_complete(coro)
            finally:
                loop.close()
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        raise TimeoutError(f"{agent_name} exceeded {timeout:.0f}s")
    if "error" in result:
        raise RuntimeError(result["error"])
    return str(result.get("value", ""))


def build_tests() -> list[TestCase]:
    tests: list[TestCase] = []

    # ---------------- Infrastructure ----------------
    def t_config():
        from agents.config import Config
        Config.ensure_dirs()
        return f"log_level={Config.LOG_LEVEL} db={Config.DB_PATH}"
    tests.append(TestCase("config.load", "infrastructure", t_config, needs_registry=False))

    def t_env_loader():
        from agents.env_loader import load_env
        env = load_env()
        return f"loaded {len(env)} keys"
    tests.append(TestCase("env_loader.load", "infrastructure", t_env_loader, needs_registry=False))

    def t_database():
        from agents.persistence import Database, AuditRepository
        from agents.schemas import AuditEntry
        async def _go():
            db = Database(":memory:")
            await db.connect()
            repo = AuditRepository(db)
            await repo.add(AuditEntry(event="harness.probe"))
            rows = await repo.recent(limit=5)
            await db.close()
            return f"{len(rows)} audit rows"
        return asyncio.run(_go())
    tests.append(TestCase("database.roundtrip", "infrastructure", t_database, needs_registry=False))

    def t_bus():
        from agents.message_bus import MessageBus
        bus = MessageBus()
        bus.send("harness", {"type": "ping"})
        got = bus.receive("harness", timeout=0.5)
        bus.stop()
        return f"received={got is not None and got.get('type')=='ping'}"
    tests.append(TestCase("message_bus.send_receive", "infrastructure", t_bus, needs_registry=False))

    def t_registry_stats(registry=None):
        n = len(registry.all()) if registry else 0
        return f"{n} agents registered"
    tests.append(TestCase("registry.list", "infrastructure", t_registry_stats, timeout=5))

    # ---------------- Core reasoning agents ----------------
    tests.append(TestCase("planner.plan",
        "reasoning",
        lambda r=None: _call_agent(r, "PlannerAgent", "plan", "search for maize prices"),
        timeout=30))
    tests.append(TestCase("thinker.think",
        "reasoning",
        lambda r=None: _call_agent(r, "ThinkerAgent", "run", "what is 2+2"),
        timeout=15))
    tests.append(TestCase("debater.challenge",
        "reasoning",
        lambda r=None: _call_agent(r, "DebaterAgent", "run",
                                   "This answer is thorough enough for a simple question."),
        timeout=15))
    tests.append(TestCase("critic.evaluate",
        "reasoning",
        lambda r=None: _call_agent(r, "CriticAgent", "run",
                                   [["step1", "a sufficiently long result"]]),
        timeout=15))
    tests.append(TestCase("sentiment.analyze",
        "reasoning",
        lambda r=None: _call_agent(r, "SentimentAgent", "analyze", "I love this"),
        timeout=10))
    tests.append(TestCase("validate.check",
        "reasoning",
        lambda r=None: _call_agent(r, "InputValidationAgent", "check",
                                   "<script>alert(1)</script>"),
        timeout=10))
    tests.append(TestCase("knowledge.ask",
        "reasoning",
        lambda r=None: _call_agent(r, "KnowledgeAgent", "run", "what is python"),
        timeout=10))
    tests.append(TestCase("summarize.short",
        "reasoning",
        lambda r=None: _call_agent(r, "SummarizerAgent", "summarize",
                                   "Python is a general purpose language created in 1991 "
                                   "and used widely for scripting, data science and web.",
                                   "short"),
        timeout=45))

    # ---------------- Pipeline ----------------
    def t_pipeline(registry=None):
        from agents.browser import SimpleBrowser
        from agents.executor_agent import ExecutorAgent
        ex = ExecutorAgent(browser=SimpleBrowser(), bus=None, registry=registry)
        results = ex.run(["search for python tutorials"], goal="harness")
        return f"{len(results)} step(s): {results[0][1][:60]!r}"
    tests.append(TestCase("pipeline.executor", "pipeline", t_pipeline, timeout=45))

    # ---------------- Data / search ----------------
    tests.append(TestCase("search.tavily",
        "data",
        lambda r=None: _call_agent(r, "SearchAgent", "run", "kenya farming news"),
        timeout=30))
    tests.append(TestCase("web.fetch",
        "data",
        lambda r=None: _call_agent(r, "WebAgent", "run", "https://example.com"),
        timeout=30))

    # ---------------- Farm / domain ----------------
    for town in ("Nakuru", "Eldoret", "Kisumu"):
        tests.append(TestCase(f"farm.brief.{town.lower()}",
            "farm",
            lambda r=None, _town=town: _call_agent(r, "FarmerDigestAgent", "run", _town,
                                                   timeout=180),
            timeout=180))

    tests.append(TestCase("disease.text",
        "farm",
        lambda r=None: _call_agent(r, "DiseaseAlertAgent", "run",
                                   "crop:maize symptoms:yellow leaves with brown spots"),
        timeout=60))

    def t_disease_image(registry=None):
        img_dir = PROJECT_ROOT / "generated_images"
        if not img_dir.exists():
            raise RuntimeError("generated_images/ missing")
        imgs = [p for p in img_dir.iterdir()
                if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        if not imgs:
            raise RuntimeError("no images in generated_images/")
        crop_hint = ("leaf", "crop", "plant", "maize", "tomato", "cassava", "disease")
        crop_img = next((p for p in imgs
                         if any(h in p.stem.lower() for h in crop_hint)), None)
        if crop_img is None:
            raise RuntimeError(
                f"no crop-like image found ({len(imgs)} generic images) - "
                "rename one to include leaf/crop/plant to exercise this test"
            )
        return _call_agent(registry, "DiseaseAlertAgent", "run", str(crop_img),
                           timeout=120)
    tests.append(TestCase("disease.image", "farm", t_disease_image, timeout=120))

    # ---------------- Voice / vision / speech ----------------
    def t_image_analysis(registry=None):
        img_dir = PROJECT_ROOT / "generated_images"
        if not img_dir.exists():
            raise RuntimeError("generated_images/ missing")
        imgs = [p for p in img_dir.iterdir()
                if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        if not imgs:
            raise RuntimeError("no images in generated_images/")
        return _call_agent(registry, "ImageAnalysisAgent", "run", str(imgs[0]),
                           timeout=120)
    tests.append(TestCase("image.analysis", "vision", t_image_analysis, timeout=120))

    def t_transcribe(registry=None):
        candidates = list((PROJECT_ROOT / "sandbox").glob("*.ogg")) + \
                     list((PROJECT_ROOT / "sandbox").glob("*.wav")) + \
                     list((PROJECT_ROOT / "sandbox").glob("*.m4a"))
        if not candidates:
            raise RuntimeError("no audio files in sandbox/")
        return _call_agent(registry, "TranscriptionAgent", "run", str(candidates[0]),
                           timeout=60)
    tests.append(TestCase("transcribe.audio", "voice", t_transcribe, timeout=60))

    tests.append(TestCase("speech.save",
        "voice",
        lambda r=None: _call_agent(r, "SpeechAgent", "run",
                                   "save: autonomous harness voice probe"),
        timeout=30))

    # ---------------- Location ----------------
    tests.append(TestCase("location.reverse",
        "location",
        lambda r=None: _call_agent(r, "LocationAgent", "run", "reverse:-0.3031,36.08"),
        timeout=15))
    tests.append(TestCase("location.forward",
        "location",
        lambda r=None: _call_agent(r, "LocationAgent", "run", "Eldoret"),
        timeout=15))

    # ---------------- Device ----------------
    tests.append(TestCase("device.list",
        "device",
        lambda r=None: _call_agent(r, "DeviceControlAgent", "run", "list"),
        timeout=10))

    # ---------------- Persistence ----------------
    tests.append(TestCase("audit.recent",
        "persistence",
        lambda r=None: _call_agent(r, "AuditAgent", "recent", 5),
        timeout=15))
    tests.append(TestCase("metrics.summary",
        "persistence",
        lambda r=None: _call_agent(r, "MetricsAgent", "summary"),
        timeout=15))
    tests.append(TestCase("session.store",
        "persistence",
        lambda r=None: _call_agent(r, "SessionAgent", "run", "harness",
                                   {"probe": "ok"}),
        timeout=15))
    tests.append(TestCase("memory.store",
        "persistence",
        lambda r=None: _call_agent(r, "MemoryAgent", "run",
                                   [("harness.test", "value-ok")]),
        timeout=15))

    # ---------------- Misc agents ----------------
    tests.append(TestCase("scheduler.list",
        "misc",
        lambda r=None: _call_agent(r, "SchedulerAgent", "list"),
        timeout=10))
    tests.append(TestCase("tagging.run",
        "misc",
        lambda r=None: _call_agent(r, "TaggingAgent", "run",
                                   {"text": "urgent bug fix"}),
        timeout=10))
    tests.append(TestCase("task.create",
        "misc",
        lambda r=None: _call_agent(r, "TaskAgent", "create",
                                   "harness_test_task"),
        timeout=10))
    tests.append(TestCase("profile.show",
        "misc",
        lambda r=None: _call_agent(r, "UserProfileAgent", "show", "harness_user"),
        timeout=10))
    tests.append(TestCase("onboarding.run",
        "misc",
        lambda r=None: _call_agent(r, "OnboardingAgent", "run", "harness_user"),
        timeout=10))
    tests.append(TestCase("priority.size",
        "misc",
        lambda r=None: _call_agent(r, "PriorityQueueAgent", "size"),
        timeout=10))
    tests.append(TestCase("roleassignment.list",
        "misc",
        lambda r=None: _call_agent(r, "RoleAssignmentAgent", "list"),
        timeout=10))
    tests.append(TestCase("security.alerts",
        "misc",
        lambda r=None: _call_agent(r, "SecurityAgent", "alerts"),
        timeout=10))
    tests.append(TestCase("feedback.run",
        "misc",
        lambda r=None: _call_agent(r, "FeedbackAgent", "run", "harness feedback"),
        timeout=10))
    tests.append(TestCase("logging.log",
        "misc",
        lambda r=None: _call_agent(r, "LoggingAgent", "run", "harness log entry"),
        timeout=10))
    tests.append(TestCase("logview.show",
        "misc",
        lambda r=None: _call_agent(r, "LogViewAgent", "show"),
        timeout=10))
    tests.append(TestCase("template.render",
        "misc",
        lambda r=None: _call_agent(r, "TemplateCompletionAgent", "render",
                                   "Hello $name", {"name": "World"}),
        timeout=10))
    tests.append(TestCase("status.run",
        "misc",
        lambda r=None: _call_agent(r, "StatusAgent", "run", ""),
        timeout=10))
    tests.append(TestCase("systemagent.whoami",
        "misc",
        lambda r=None: _call_agent(r, "SystemAgent", "run", "whoami"),
        timeout=15))
    tests.append(TestCase("filemanagement.list",
        "misc",
        lambda r=None: _call_agent(r, "FileManagementAgent", "list", "."),
        timeout=10))
    tests.append(TestCase("sample.run",
        "misc",
        lambda r=None: _call_agent(r, "SampleAgent", "run", "harness"),
        timeout=10))
    tests.append(TestCase("conversation.run",
        "misc",
        lambda r=None: _call_agent(r, "ConversationAgent", "run", "hello"),
        timeout=10))
    tests.append(TestCase("datacollection.run",
        "misc",
        lambda r=None: _call_agent(r, "DataCollectionAgent", "run",
                                   {"probe": "ok"}),
        timeout=10))
    tests.append(TestCase("integration.list",
        "misc",
        lambda r=None: _call_agent(r, "IntegrationAgent", "list"),
        timeout=10))
    tests.append(TestCase("notification.run",
        "misc",
        lambda r=None: _call_agent(r, "NotificationAgent", "run",
                                   "harness notification"),
        timeout=20))
    tests.append(TestCase("sessiontimeout.list",
        "misc",
        lambda r=None: _call_agent(r, "SessionTimeoutAgent", "list"),
        timeout=10))
    tests.append(TestCase("control.list",
        "misc",
        lambda r=None: _call_agent(r, "ControlAgent", "list"),
        timeout=10))
    tests.append(TestCase("route.health",
        "misc",
        lambda r=None: _call_agent(r, "CommandRoutingAgent", "run", "health"),
        timeout=15))
    tests.append(TestCase("eventdispatch.list",
        "misc",
        lambda r=None: _call_agent(r, "EventDispatchAgent", "list"),
        timeout=10))

    # ---------------- LLM direct ----------------
    def t_llm(registry=None):
        from agents.llm import get_llm
        llm = get_llm()
        async def _go():
            return await llm.chat([{"role": "user", "content": "Say OK and nothing else."}])
        text = asyncio.run(_go())
        return f"llm reply: {text[:60]!r}"
    tests.append(TestCase("llm.chat", "llm", t_llm, timeout=30, needs_registry=False))

    # --- extension categories: router, nosignup, plugins, memory, orchestrator ---
    try:
        from harness_extensions import build_extension_tests
        tests.extend(build_extension_tests())
    except Exception as _e:
        print(f"[harness] extension tests failed to load: {_e}")

    return tests


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_single(test: TestCase, registry) -> dict:
    start = time.perf_counter()
    record = {
        "name": test.name,
        "category": test.category,
        "status": "unknown",
        "duration_ms": 0.0,
        "detail": "",
    }
    try:
        if test.needs_registry:
            result = test.fn(registry)
        else:
            result = test.fn()
        record["status"] = "pass"
        record["detail"] = str(result)[:200]
    except TimeoutError as e:
        record["status"] = "timeout"
        record["detail"] = str(e)
    except Exception as e:
        record["status"] = "fail"
        record["detail"] = f"{type(e).__name__}: {e}"
        record["trace"] = traceback.format_exc().splitlines()[-3:]
    record["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return record


def build_report(run_id: str, started: datetime, ended: datetime,
                 rounds: int, records: list[dict], meta: dict) -> tuple[Path, Path]:
    total = len(records)
    passed = sum(1 for r in records if r["status"] == "pass")
    failed = sum(1 for r in records if r["status"] == "fail")
    timed_out = sum(1 for r in records if r["status"] == "timeout")

    by_cat: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for r in records:
        c = by_cat.setdefault(r["category"], {"pass": 0, "fail": 0, "timeout": 0, "total": 0})
        c[r["status"]] = c.get(r["status"], 0) + 1
        c["total"] += 1
        n = by_name.setdefault(r["name"], {"pass": 0, "fail": 0, "timeout": 0, "total": 0})
        n[r["status"]] = n.get(r["status"], 0) + 1
        n["total"] += 1

    md: list[str] = []
    md.append(f"# Autonomous Test Report")
    md.append("")
    md.append(f"- **Run ID:** `{run_id}`")
    md.append(f"- **Started:** {started.isoformat(timespec='seconds')}")
    md.append(f"- **Ended:** {ended.isoformat(timespec='seconds')}")
    md.append(f"- **Duration:** {(ended-started).total_seconds():.0f}s")
    md.append(f"- **Rounds completed:** {rounds}")
    md.append(f"- **Total test invocations:** {total}")
    md.append(f"- **Passed:** {passed}  **Failed:** {failed}  **Timed out:** {timed_out}")
    md.append(f"- **Platform:** {meta.get('platform')}  **Python:** {meta.get('python')}")
    md.append("")

    md.append("## Summary by category")
    md.append("")
    md.append("| Category | Total | Pass | Fail | Timeout |")
    md.append("|---|---|---|---|---|")
    for cat in sorted(by_cat):
        c = by_cat[cat]
        md.append(f"| {cat} | {c['total']} | {c.get('pass',0)} | {c.get('fail',0)} | {c.get('timeout',0)} |")
    md.append("")

    md.append("## Summary by test")
    md.append("")
    md.append("| Test | Total | Pass | Fail | Timeout |")
    md.append("|---|---|---|---|---|")
    for name in sorted(by_name):
        n = by_name[name]
        md.append(f"| {name} | {n['total']} | {n.get('pass',0)} | {n.get('fail',0)} | {n.get('timeout',0)} |")
    md.append("")

    md.append("## Failures (unique)")
    md.append("")
    seen = set()
    any_fail = False
    for r in records:
        if r["status"] == "pass":
            continue
        key = (r["name"], r["status"], r["detail"][:80])
        if key in seen:
            continue
        seen.add(key)
        any_fail = True
        md.append(f"### `{r['name']}` — {r['status']} ({r['duration_ms']}ms)")
        md.append("```")
        md.append(r["detail"])
        md.append("```")
        md.append("")
    if not any_fail:
        md.append("_No failures. 🎉_")
        md.append("")

    md.append("## Full invocation log")
    md.append("")
    md.append("| # | Time | Test | Status | Duration (ms) | Detail |")
    md.append("|---|---|---|---|---|---|")
    base = started.timestamp()
    for i, r in enumerate(records, 1):
        t = datetime.fromtimestamp(base + i * 0.001, tz=timezone.utc).strftime("%H:%M:%S")
        detail = r["detail"].replace("|", "\\|").replace("\n", " ")[:120]
        md.append(f"| {i} | {t} | `{r['name']}` | {r['status']} | {r['duration_ms']} | {detail} |")
    md.append("")

    text = "\n".join(md)
    stamp = ended.strftime("%Y-%m-%d_%H%M%S")
    md_path = REPORT_DIR / f"harness_{stamp}.md"
    json_path = REPORT_DIR / f"harness_{stamp}.json"
    md_path.write_text(text, encoding="utf-8")
    json_path.write_text(json.dumps({
        "run_id": run_id,
        "started": started.isoformat(),
        "ended": ended.isoformat(),
        "rounds": rounds,
        "summary": {
            "total": total, "passed": passed, "failed": failed, "timed_out": timed_out,
            "by_category": by_cat, "by_test": by_name,
        },
        "meta": meta,
        "records": records,
    }, indent=2, default=str), encoding="utf-8")
    return md_path, json_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--rounds", type=int, default=0,
                    help="0 = loop until time; >0 = fixed number of rounds")
    ap.add_argument("--quick", action="store_true",
                    help="shortcut: 5 minutes, log each test as it runs")
    ap.add_argument("--only", type=str, default=None,
                    help="run only tests in this category (router|nosignup|plugins|memory|orchestrator|meta|moderouter|...)")
    args = ap.parse_args()

    if args.quick:
        args.minutes = 5.0

    run_id = uuid.uuid4().hex[:10]
    started = datetime.now(timezone.utc)
    deadline = time.time() + args.minutes * 60

    print(f"[harness] run_id={run_id} budget={args.minutes:.0f} min")
    tests = build_tests()
    if args.only:
        tests = [t for t in tests
                 if t.category == args.only or t.name.startswith(args.only + ".")]
        if not tests:
            print(f"[harness] no tests matched --only {args.only!r}")
            return 1
    print(f"[harness] {len(tests)} tests defined")
    needs_registry = any(t.needs_registry for t in tests)
    if not needs_registry:
        print("[harness] no tests need the agent registry - skipping build")
        db = bus = registry = None
    else:
        print("[harness] building registry …")
        from agents.config import Config
        from agents.persistence import Database
        from agents.message_bus import MessageBus
        from agents.api_server import build_registry

        Config.ensure_dirs()
        async def _build():
            db = Database(Config.DB_PATH)
            await db.connect()
            bus = MessageBus()
            reg = build_registry(bus=bus, db=db)
            return db, bus, reg
        db, bus, registry = asyncio.run(_build())
        print(f"[harness] {len(registry.all())} agents registered")

    print()

    records: list[dict] = []
    rounds = 0

    try:
        while True:
            rounds += 1
            print(f"===== Round {rounds} =====")
            for test in tests:
                if time.time() >= deadline:
                    print("[harness] budget reached, stopping")
                    raise KeyboardInterrupt
                record = run_single(test, registry)
                records.append(record)
                icon = {"pass": "✅", "fail": "❌", "timeout": "⏱️"}.get(record["status"], "?")
                print(f"  {icon} {record['name']:<32s} {record['duration_ms']:>7.1f}ms  {record['detail'][:70]}")
            if args.rounds and rounds >= args.rounds:
                break
    except KeyboardInterrupt:
        print("[harness] stopping")

    ended = datetime.now(timezone.utc)
    meta = {
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": platform.python_version(),
        "minutes_budget": args.minutes,
    }
    md_path, json_path = build_report(run_id, started, ended, rounds, records, meta)

    # stop background threads
    try:
        bus.stop()
        registry.shutdown()
        asyncio.run(db.close())
    except Exception:
        pass

    print()
    print(f"[harness] report written: {md_path}")
    print(f"[harness] json  written: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
