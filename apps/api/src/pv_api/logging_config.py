"""Structured JSON logging.

Only an allowlist of fields is emitted. Request bodies, query strings, headers
and resume content are never logged (docs/security/threat-model.md, T14).
Moves to packages/observability in checkpoint 1.4.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    _EXTRA_FIELDS = ("request_id", "method", "path", "status", "duration_ms")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in self._EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # We log each request ourselves, with a request id and duration.
    logging.getLogger("uvicorn.access").disabled = True
