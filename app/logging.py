"""Structured JSON logging with a per-request correlation id.

One JSON object per line, machine-parseable by any aggregator with no shipping
agent. Dependency-free on purpose. Stdlib logging is enough.
"""

from __future__ import annotations

import contextvars
import datetime as dt
import json
import logging
import sys
from typing import Any

correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": dt.datetime.fromtimestamp(record.created, tz=dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = correlation_id.get()
        if cid:
            payload["correlation_id"] = cid
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
