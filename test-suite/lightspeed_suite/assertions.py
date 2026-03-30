from __future__ import annotations

from typing import Any


def event_by_name(events: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for event in events:
        if event.get("event") == name:
            return event
    return None


def require_event(events: list[dict[str, Any]], name: str) -> dict[str, Any]:
    event = event_by_name(events, name)
    assert event is not None, f"Expected event={name!r}, got events: {list_event_names(events)}"
    return event


def list_event_names(events: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("event")) for item in events]


def extract_start_ids(events: list[dict[str, Any]]) -> tuple[str, str]:
    start = require_event(events, "start")
    data = start.get("data", {})
    conversation_id = data.get("conversation_id")
    request_id = data.get("request_id")
    assert isinstance(conversation_id, str) and conversation_id, (
        "Missing conversation_id in start event"
    )
    assert isinstance(request_id, str) and request_id, "Missing request_id in start event"
    return conversation_id, request_id

