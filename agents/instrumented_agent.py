"""Mixin that wraps every agent call in an OTel span + metrics."""
from __future__ import annotations

import time
from typing import Any

from agents.telemetry import get_meter, get_tracer
from agents.tracing import get_trace_id, get_user_id

_tracer = get_tracer("agents")
_meter = get_meter("agents")

_calls = _meter.create_counter("agent.calls", description="Agent invocations")
_errors = _meter.create_counter("agent.errors", description="Agent errors")
_latency = _meter.create_histogram("agent.latency_ms", unit="ms", description="Agent latency")


class InstrumentedAgent:
    """Mix into any agent to get free spans and metrics on arun/ahandle_command."""

    async def arun(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        return await self._traced("run", self._run_impl, *args, **kwargs)

    async def ahandle_command(self, command: str, *args: Any) -> Any:  # type: ignore[override]
        return await self._traced("command", self._cmd_impl, command, *args)

    async def _traced(self, kind: str, fn, *args: Any, **kwargs: Any) -> Any:
        name = getattr(self, "name", self.__class__.__name__)
        attrs = {
            "agent.name": name,
            "agent.kind": kind,
            "trace_id": get_trace_id(),
            "user_id": get_user_id() or "",
        }
        start = time.perf_counter()
        with _tracer.start_as_current_span(f"agent.{name}.{kind}", attributes=attrs) as span:
            try:
                result = await fn(*args, **kwargs)
                _calls.add(1, {"agent": name, "kind": kind, "status": "ok"})
                return result
            except Exception as exc:
                _errors.add(1, {"agent": name, "kind": kind})
                span.record_exception(exc)
                span.set_attribute("error", str(exc))
                raise
            finally:
                ms = (time.perf_counter() - start) * 1000
                _latency.record(ms, {"agent": name, "kind": kind})

    # Subclasses wire these to their real methods
    async def _run_impl(self, *args, **kwargs):
        raise NotImplementedError

    async def _cmd_impl(self, command, *args):
        raise NotImplementedError