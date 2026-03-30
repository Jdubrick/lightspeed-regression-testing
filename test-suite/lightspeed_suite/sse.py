from __future__ import annotations

import json
from typing import Any


def parse_sse_lines(lines: list[str]) -> list[dict[str, Any]]:
    """Parse SSE payloads from raw response lines.

    The API emits SSE chunks where each event usually appears in a `data:` line that
    itself contains JSON (including an `event` field). We keep this parser permissive
    so tests can validate schema while tolerating minor format differences.
    """
    events: list[dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            payload = line[5:].strip()
        else:
            payload = line

        if payload == "[DONE]":
            continue

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            events.append(parsed)
    return events

