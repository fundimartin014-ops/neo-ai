"""Structured JSON logging with trace_id / user_id auto-injected."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from agents.tracing import get_trace_id, get_user_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": get_trace_id(),
            "user_id": get_user_id() or None,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # structured extra fields
        for key in ("agent", "command", "duration_ms", "goal", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        extra = record.__dict__.get("extra")
        if isinstance(extra, dict):
            payload.update(extra)

        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [%(trace_id)s]: %(message)s"
            )
        )
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ("uvicorn.access", "aiosqlite"):
        logging.getLogger(noisy).setLevel("WARNING")