from __future__ import annotations

from agents.env_loader import load_env
load_env()  # populate os.environ from .env (shell env wins)

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from agents.config import Config
from agents.logging_setup import setup_logging
from agents.message_bus import MessageBus
from agents.persistence import (
    AuditRepository,
    Database,
    MemoryRepository,
    MetricsRepository,
    SessionRepository,
)
from agents.registry import AgentRegistry
from agents.schemas import CommandRequest, CommandResponse, HealthReport
from agents.tracing import new_trace_id, set_trace_id, set_user_id

VERSION = "0.2.0"


# ---- registry builder (shared with CLI) -----------------------------------
def build_registry(bus: MessageBus, db: Database) -> AgentRegistry:
    from agents.knowledge_agent import KnowledgeAgent  # patched
    # KnowledgeAgent (added by patch)
    # import here so tests can reuse
    from agents.audit_agent import AuditAgent
    from agents.memory_agent import MemoryAgent
    from agents.metrics_agent import MetricsAgent
    from agents.session_agent import SessionAgent
    from agents.planner_agent import PlannerAgent
    from agents.critic_agent import CriticAgent
    from agents.executor_agent import ExecutorAgent
    from agents.thinker_agent import ThinkerAgent
    from agents.debater_agent import DebaterAgent
    from agents.control_agent import ControlAgent
    from agents.command_routing_agent import CommandRoutingAgent
    from agents.event_dispatch_agent import EventDispatchAgent
    from agents.web_agent import WebAgent
    from agents.search_agent import SearchAgent
    from agents.summarizer_agent import SummarizerAgent
    from agents.sentiment_agent import SentimentAgent
    from agents.input_validation_agent import InputValidationAgent
    from agents.browser import SimpleBrowser
    # additional agents
    from agents.api_agent import APIAgent
    from agents.conversation_agent import ConversationAgent
    from agents.data_collection_agent import DataCollectionAgent
    from agents.feedback_agent import FeedbackAgent
    from agents.file_management_agent import FileManagementAgent
    from agents.integration_agent import IntegrationAgent
    from agents.log_view_agent import LogViewAgent
    from agents.logging_agent import LoggingAgent
    from agents.notification_agent import NotificationAgent
    from agents.onboarding_agent import OnboardingAgent
    from agents.priority_queue_agent import PriorityQueueAgent
    from agents.role_assignment_agent import RoleAssignmentAgent
    from agents.sample_agent import SampleAgent
    from agents.security_agent import SecurityAgent
    from agents.session_timeout_agent import SessionTimeoutAgent
    from agents.status_agent import StatusAgent
    from agents.system_agent import SystemAgent
    from agents.tagging_agent import TaggingAgent
    from agents.task_agent import TaskAgent
    from agents.template_completion_agent import TemplateCompletionAgent
    from agents.user_profile_agent import UserProfileAgent
    # additional agents

    reg = AgentRegistry()
    reg.register(KnowledgeAgent())  # patched


    reg.register(EventDispatchAgent(bus=bus))
    reg.register(ControlAgent(registry=reg, bus=bus))

    reg.register(PlannerAgent(bus=bus))
    reg.register(ExecutorAgent(browser=SimpleBrowser(), registry=reg, bus=bus))
    reg.register(CriticAgent(bus=bus))
    reg.register(MemoryAgent(repo=MemoryRepository(db), bus=bus))
    reg.register(ThinkerAgent(bus=bus))
    reg.register(DebaterAgent(bus=bus))

    reg.register(AuditAgent(repo=AuditRepository(db), bus=bus))
    reg.register(SessionAgent(repo=SessionRepository(db), bus=bus))
    reg.register(MetricsAgent(repo=MetricsRepository(db), bus=bus))

    reg.register(WebAgent(bus=bus))
    reg.register(SearchAgent(bus=bus))
    from agents.disease_alert_agent import DiseaseAlertAgent
    reg.register(DiseaseAlertAgent(bus=bus))
    from agents.image_analysis_agent import ImageAnalysisAgent
    reg.register(ImageAnalysisAgent(bus=bus))
    from agents.transcription_agent import TranscriptionAgent
    reg.register(TranscriptionAgent(bus=bus))
    from agents.location_agent import LocationAgent
    reg.register(LocationAgent(bus=bus))
    from agents.speech_agent import SpeechAgent
    reg.register(SpeechAgent(bus=bus))
    from agents.device_control_agent import DeviceControlAgent
    reg.register(DeviceControlAgent(bus=bus))
    reg.register(SummarizerAgent(bus=bus))
    from agents.farmer_digest_agent import FarmerDigestAgent
    reg.register(FarmerDigestAgent(bus=bus, registry=reg))
    from agents.scheduler_agent import SchedulerAgent
    reg.register(SchedulerAgent(db=db, bus=bus))
    from agents.market_agent import MarketAgent
    reg.register(MarketAgent(db=db, bus=bus))
    reg.register(SentimentAgent(bus=bus))
    reg.register(InputValidationAgent(bus=bus))

    router = CommandRoutingAgent(registry=reg, bus=bus)
    router.add_agent_route("health", "ControlAgent", "health")
    router.add_agent_route("audit_recent", "AuditAgent", "recent")
    router.add_agent_route("metrics_summary", "MetricsAgent", "summary")
    router.add_agent_route("sentiment", "SentimentAgent", "analyze")
    router.add_agent_route("validate", "InputValidationAgent", "check")
    router.add_agent_route("web_fetch", "WebAgent", "fetch")
    reg.register(router)
    # additional registrations
    reg.register(APIAgent(bus=bus))
    reg.register(ConversationAgent(bus=bus))
    reg.register(DataCollectionAgent(bus=bus))
    reg.register(FeedbackAgent(bus=bus))
    reg.register(FileManagementAgent(bus=bus))
    reg.register(IntegrationAgent(bus=bus))
    reg.register(LogViewAgent(bus=bus))
    reg.register(LoggingAgent(bus=bus))
    reg.register(NotificationAgent(bus=bus))
    reg.register(OnboardingAgent(bus=bus))
    reg.register(PriorityQueueAgent(bus=bus))
    reg.register(RoleAssignmentAgent(bus=bus))
    reg.register(SampleAgent(bus=bus))
    reg.register(SecurityAgent(bus=bus))
    reg.register(SessionTimeoutAgent(bus=bus))
    reg.register(StatusAgent(bus=bus))
    reg.register(SystemAgent(bus=bus))
    reg.register(TaggingAgent(bus=bus))
    reg.register(TaskAgent(bus=bus))
    reg.register(TemplateCompletionAgent(bus=bus))
    reg.register(UserProfileAgent(bus=bus))
    # additional registrations
    reg.register(APIAgent(bus=bus))
    reg.register(ConversationAgent(bus=bus))
    reg.register(DataCollectionAgent(bus=bus))
    reg.register(FeedbackAgent(bus=bus))
    reg.register(FileManagementAgent(bus=bus))
    reg.register(IntegrationAgent(bus=bus))
    reg.register(LogViewAgent(bus=bus))
    reg.register(LoggingAgent(bus=bus))
    reg.register(NotificationAgent(bus=bus))
    reg.register(OnboardingAgent(bus=bus))
    reg.register(PriorityQueueAgent(bus=bus))
    reg.register(RoleAssignmentAgent(bus=bus))
    reg.register(SampleAgent(bus=bus))
    reg.register(SecurityAgent(bus=bus))
    reg.register(SessionTimeoutAgent(bus=bus))
    reg.register(StatusAgent(bus=bus))
    reg.register(SystemAgent(bus=bus))
    reg.register(TaggingAgent(bus=bus))
    reg.register(TaskAgent(bus=bus))
    reg.register(TemplateCompletionAgent(bus=bus))
    reg.register(UserProfileAgent(bus=bus))
    return reg


# ---- lifespan --------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    from agents.telemetry import setup_telemetry
    setup_telemetry(app=app)
    setup_logging(level=Config.LOG_LEVEL, json_output=Config.LOG_JSON)
    db = Database(Config.DB_PATH)
    await db.connect()
    bus = MessageBus()
    registry = build_registry(bus=bus, db=db)

    # start background pipeline consumers
    for name in ("ExecutorAgent", "CriticAgent", "MemoryAgent"):
        agent = registry.get(name)
        if agent and hasattr(agent, "start"):
            agent.start()

    app.state.db = db
    app.state.bus = bus
    app.state.registry = registry
    app.state.started_at = time.perf_counter()
    from agents.scheduler_worker import start_worker, stop_worker
    start_worker(registry)

    try:
        yield
    finally:
        await stop_worker()
        bus.stop()
        registry.shutdown()
        await db.close()


app = FastAPI(title="Multiagent Runtime", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



# ---- middleware ------------------------------------------------------------
@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    tid = request.headers.get("x-trace-id") or new_trace_id()
    set_trace_id(tid)
    set_user_id(request.headers.get("x-user-id", ""))
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "trace_id": tid},
            headers={"x-trace-id": tid},
        )
    response.headers["x-trace-id"] = tid
    response.headers["x-duration-ms"] = f"{(time.perf_counter() - start) * 1000:.2f}"
    return response


# ---- endpoints -------------------------------------------------------------
@app.get("/health", response_model=HealthReport)
async def health(request: Request) -> HealthReport:
    reg: AgentRegistry = request.app.state.registry
    return HealthReport(
        status="ok",
        agents={n: a.health() for n, a in reg.all().items()},
        uptime_s=time.perf_counter() - request.app.state.started_at,
        version=VERSION,
    )


@app.get("/agents")
async def list_agents(request: Request) -> list[str]:
    return sorted(request.app.state.registry.all().keys())


@app.post("/command", response_model=CommandResponse)
async def command(req: CommandRequest, request: Request) -> CommandResponse:
    if req.trace_id:
        set_trace_id(req.trace_id)
    if req.user_id:
        set_user_id(req.user_id)

    reg: AgentRegistry = request.app.state.registry
    if not reg.get(req.agent):
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent}' not found")

    start = time.perf_counter()
    try:
        result = await reg.acommand(req.agent, req.command, *req.args)
        duration = (time.perf_counter() - start) * 1000
        try:
            await reg.arun("AuditAgent", "command.ok", {
                "agent": req.agent,
                "command": req.command,
                "duration_ms": duration,
            })
        except Exception:
            pass
        try:
            await reg.arun("MetricsAgent", "command_duration_ms", duration, {
                "agent": req.agent,
                "command": req.command,
                "ok": "true",
            })
        except Exception:
            pass
        return CommandResponse(
            ok=True,
            agent=req.agent,
            command=req.command,
            result=result,
            trace_id=_current_trace(),
            duration_ms=duration,
        )
    except Exception as exc:  # noqa: BLE001
        duration = (time.perf_counter() - start) * 1000
        try:
            await reg.arun("AuditAgent", "command.error", {
                "agent": req.agent,
                "command": req.command,
                "error": str(exc),
                "duration_ms": duration,
            })
        except Exception:
            pass
        try:
            await reg.arun("MetricsAgent", "command_duration_ms", duration, {
                "agent": req.agent,
                "command": req.command,
                "ok": "false",
            })
        except Exception:
            pass
        return CommandResponse(
            ok=False,
            agent=req.agent,
            command=req.command,
            error=str(exc),
            trace_id=_current_trace(),
            duration_ms=duration,
        )

@app.get("/metrics")
async def metrics_summary(request: Request):
    reg: AgentRegistry = request.app.state.registry
    return await reg.acommand("MetricsAgent", "summary")


@app.get("/audit")
async def audit_recent(request: Request, limit: int = 50):
    reg: AgentRegistry = request.app.state.registry
    return await reg.acommand("AuditAgent", "recent", limit)



async def write_audit(request: Request, body: dict[str, Any]) -> dict:
    from agents.schemas import AuditEntry

    reg: AgentRegistry = request.app.state.registry
    entry = AuditEntry(**body)
    await reg.arun("AuditAgent", entry.event, entry.details)
    return {"ok": True}


def _current_trace() -> str:
    from agents.tracing import get_trace_id

    return get_trace_id()

# ---------------------------------------------------------------------------
# Synchronous goal runner — used by the browser UI
# ---------------------------------------------------------------------------
@app.post("/run")
async def run_goal(request: Request, body: dict) -> dict:
    import json as _json

    goal = (body.get("goal") or "").strip()
    if not goal:
        raise HTTPException(status_code=400, detail="missing 'goal'")

    reg: AgentRegistry = request.app.state.registry

    # 1. plan
    try:
        plan_raw = await reg.acommand("PlannerAgent", "plan", goal)
        if isinstance(plan_raw, str):
            plan_data = _json.loads(plan_raw)
        else:
            plan_data = plan_raw
        steps = plan_data.get("steps") or [goal]
    except Exception as exc:
        steps = [goal]
        plan_error = str(exc)
    else:
        plan_error = None

    # 2. execute
    executor = reg.get("ExecutorAgent")
    if executor is None:
        return {"goal": goal, "error": "ExecutorAgent not registered", "plan": steps}

    try:
        raw_results = executor.run(steps, goal=goal)
    except Exception as exc:
        return {"goal": goal, "plan": steps, "error": f"execution failed: {exc}"}

    # 3. store to memory
    memory = reg.get("MemoryAgent")
    if memory is not None:
        try:
            await memory.arun(raw_results)
        except Exception:
            pass

    return {
        "goal": goal,
        "plan": steps,
        "plan_error": plan_error,
        "results": [{"step": s, "result": r} for s, r in raw_results],
    }


# ---------------------------------------------------------------------------
# Serve the browser UI
# ---------------------------------------------------------------------------
@app.get("/")
async def ui_root():
    from pathlib import Path as _P
    html = _P(__file__).parent / "ui.html"
    if not html.exists():
        return {"error": "ui.html not found", "path": str(html)}
    return FileResponse(str(html), media_type="text/html")


# ---------------------------------------------------------------------------
# Scheduler endpoints
# ---------------------------------------------------------------------------
@app.get("/schedules")
async def list_schedules(request: Request):
    reg: AgentRegistry = request.app.state.registry
    agent = reg.get("SchedulerAgent")
    if not agent:
        raise HTTPException(status_code=500, detail="SchedulerAgent not registered")
    return await agent.list_jobs()


@app.post("/schedules")
async def create_schedule(request: Request, body: dict):
    name = (body.get("name") or "").strip()
    schedule = (body.get("schedule") or "").strip()
    goal = (body.get("goal") or "").strip()
    if not (name and schedule and goal):
        raise HTTPException(status_code=400, detail="need name, schedule, goal")
    reg: AgentRegistry = request.app.state.registry
    agent = reg.get("SchedulerAgent")
    if not agent:
        raise HTTPException(status_code=500, detail="SchedulerAgent not registered")
    try:
        result = await agent.create(name, schedule, goal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "result": result}


@app.delete("/schedules/{job_id}")
async def delete_schedule(job_id: int, request: Request):
    reg: AgentRegistry = request.app.state.registry
    agent = reg.get("SchedulerAgent")
    if not agent:
        raise HTTPException(status_code=500, detail="SchedulerAgent not registered")
    return {"ok": True, "result": await agent.delete(job_id)}


@app.post("/schedules/{job_id}/run")
async def run_schedule_now(job_id: int, request: Request):
    """Trigger a job immediately, regardless of next_run. Useful for testing."""
    from agents.scheduler_worker import _run_goal
    reg: AgentRegistry = request.app.state.registry
    agent = reg.get("SchedulerAgent")
    if not agent:
        raise HTTPException(status_code=500, detail="SchedulerAgent not registered")
    row = await agent.db.fetchone(
        "SELECT id, name, schedule, goal FROM scheduled_jobs WHERE id = ?", (job_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"No job {job_id}")
    result = await _run_goal(reg, row["goal"])
    await agent.mark_run(row["id"], "manual", row["schedule"])
    return {"ok": True, "job_id": job_id, "name": row["name"], "result": result}


@app.get("/schedules/list")
async def list_schedules_json(request: Request):
    """Structured list for the UI."""
    reg: AgentRegistry = request.app.state.registry
    agent = reg.get("SchedulerAgent")
    if not agent:
        raise HTTPException(status_code=500, detail="SchedulerAgent not registered")
    rows = await agent.db.fetchall(
        "SELECT id, name, schedule, goal, enabled, last_run, last_result, next_run, created_at "
        "FROM scheduled_jobs ORDER BY id DESC"
    )
    return [dict(r) for r in rows]


@app.patch("/schedules/{job_id}")
async def update_schedule(job_id: int, request: Request, body: dict):
    reg: AgentRegistry = request.app.state.registry
    agent = reg.get("SchedulerAgent")
    if not agent:
        raise HTTPException(status_code=500, detail="SchedulerAgent not registered")
    if "enabled" in body:
        result = await agent.enable(job_id, bool(body["enabled"]))
        return {"ok": True, "result": result}
    raise HTTPException(status_code=400, detail="no updatable fields")
