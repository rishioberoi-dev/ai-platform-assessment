from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import LOGS_DIR


def utc_now_iso() -> str:
    # pseudo: keep timestamps in UTC so logs are consistent across environments
    return datetime.now(timezone.utc).isoformat()


def append_audit_log(
    event_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> Path:
    # pseudo: write one audit event as a single JSON line
    # json lines format is useful because it is easy to append and easy to parse later
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "audit.log"

    entry = {
        "timestamp_utc": utc_now_iso(),
        "event_type": event_type,
        "message": message,
        "metadata": metadata or {},
    }
    # pseudo: keep base structure small but useful
    # timestamp = when it happened
    # event_type = what kind of pipeline event it was
    # message = quick human-readable summary
    # metadata = structured details for debugging / audits

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    # pseudo: append mode so each new event is added to the end of the log
    # one JSON object per line keeps it simple for later grep / parsing / ingestion

    return log_path