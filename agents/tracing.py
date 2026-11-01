"""Trace / user context propagated via contextvars across sync and async code."""
from __future__ import annotations

import contextvars
from uuid import uuid4

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
_user_id: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")


def new_trace_id() -> str:
    tid = uuid4().hex
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    tid = _trace_id.get()
    return tid if tid else new_trace_id()


def set_trace_id(tid: str) -> None:
    _trace_id.set(tid or "")


def get_user_id() -> str:
    return _user_id.get()


def set_user_id(uid: str) -> None:
    _user_id.set(uid or "")