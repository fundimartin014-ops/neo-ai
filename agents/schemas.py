from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessageType(str, Enum):
    PLAN = "plan"
    RESULTS = "results"
    STORE = "store"
    GOAL = "goal"
    EVENT = "event"
    SHUTDOWN = "__shutdown__"


class Message(BaseModel):
    """Standard envelope for anything travelling on the bus."""
    type: MessageType | str
    data: Any = None
    goal: str | None = None
    sender: str | None = None
    trace_id: str = Field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = Field(default_factory=_utcnow)


class CommandRequest(BaseModel):
    agent: str
    command: str
    args: list[Any] = Field(default_factory=list)
    trace_id: str | None = None
    user_id: str | None = None


class CommandResponse(BaseModel):
    ok: bool
    agent: str
    command: str
    result: Any = None
    error: str | None = None
    trace_id: str
    duration_ms: float


class HealthReport(BaseModel):
    status: Literal["ok", "degraded", "down"]
    agents: dict[str, Any]
    uptime_s: float
    version: str


class AuditEntry(BaseModel):
    event: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    user_id: str | None = None
    timestamp: datetime = Field(default_factory=_utcnow)


class Metric(BaseModel):
    name: str
    value: float
    tags: dict[str, str] = Field(default_factory=dict)
    trace_id: str | None = None
    timestamp: datetime = Field(default_factory=_utcnow)


class MemoryItem(BaseModel):
    key: str
    value: Any
    tags: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)