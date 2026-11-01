"""OpenTelemetry bootstrap.

Usage:
    setup_telemetry(app=fastapi_app)  # called from lifespan or after app creation

If OTEL_EXPORTER_OTLP_ENDPOINT is set, spans ship via gRPC to that endpoint.
Otherwise they print to stdout via ConsoleSpanExporter.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)
_initialized = False


def setup_telemetry(
    service_name: str = "multiagent",
    app: Any = None,
    force_console: bool = False,
) -> Any:
    global _initialized
    if _initialized:
        logger.info("telemetry already initialized, skipping")
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError as e:
        print(f"[telemetry] opentelemetry not installed: {e}", file=sys.stderr)
        return None

    endpoint = (os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip()
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "0.4.0",
        "deployment.environment": os.getenv("ENV", "dev"),
    })
    provider = TracerProvider(resource=resource)

    exporter_kind = "console"
    if endpoint and not force_console:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
            )
            exporter_kind = f"otlp:{endpoint}"
        except ImportError as e:
            print(f"[telemetry] OTLP exporter missing ({e}), falling back to console", file=sys.stderr)
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    print(f"[telemetry] service={service_name} exporter={exporter_kind}", file=sys.stderr)

    # Instrument FastAPI (bind to the app if given)
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        else:
            FastAPIInstrumentor().instrument()
        print("[telemetry] FastAPI instrumented", file=sys.stderr)
    except Exception as e:
        print(f"[telemetry] FastAPI instrument skipped: {e}", file=sys.stderr)

    # Instrument logging so logger calls become span events
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=False)
    except Exception as e:
        print(f"[telemetry] logging instrument skipped: {e}", file=sys.stderr)

    _initialized = True
    return provider


def get_tracer(name: str = "multiagent"):
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return _NoopTracer()


class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def set_attribute(self, *a, **k): pass
    def set_status(self, *a, **k): pass
    def record_exception(self, *a, **k): pass


class _NoopTracer:
    def start_as_current_span(self, *a, **k): return _NoopSpan()
    def start_span(self, *a, **k): return _NoopSpan()
