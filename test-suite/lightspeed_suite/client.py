from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any

import requests

from .sse import parse_sse_lines


@dataclass
class StreamingResponse:
    status_code: int
    events: list[dict[str, Any]]
    raw_lines: list[str]
    headers: dict[str, str]


@dataclass
class ActiveStream:
    """Handle to a stream that is being consumed on a background thread."""

    response: requests.Response
    _thread: threading.Thread
    _raw_lines: list[str] = field(default_factory=list)
    _done: threading.Event = field(default_factory=threading.Event)

    def wait(self, timeout: float | None = None) -> StreamingResponse:
        self._thread.join(timeout=timeout)
        self._done.wait(timeout=0)
        events = parse_sse_lines(self._raw_lines)
        return StreamingResponse(
            status_code=self.response.status_code,
            events=events,
            raw_lines=list(self._raw_lines),
            headers=dict(self.response.headers),
        )

    @property
    def partial_events(self) -> list[dict[str, Any]]:
        return parse_sse_lines(list(self._raw_lines))


class LightspeedClient:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def get_models(self) -> requests.Response:
        return self.session.get(f"{self.base_url}/v1/models", timeout=self.timeout_seconds)

    def list_conversations(self, user_id: str) -> requests.Response:
        return self.session.get(
            f"{self.base_url}/v2/conversations",
            params={"user_id": user_id},
            timeout=self.timeout_seconds,
        )

    def get_conversation(self, conversation_id: str, user_id: str) -> requests.Response:
        return self.session.get(
            f"{self.base_url}/v2/conversations/{conversation_id}",
            params={"user_id": user_id},
            timeout=self.timeout_seconds,
        )

    def submit_feedback(self, user_id: str, payload: dict[str, Any]) -> requests.Response:
        return self.session.post(
            f"{self.base_url}/v1/feedback",
            params={"user_id": user_id},
            json=payload,
            timeout=self.timeout_seconds,
        )

    def interrupt(self, user_id: str, request_id: str) -> requests.Response:
        return self.session.post(
            f"{self.base_url}/v1/streaming_query/interrupt",
            params={"user_id": user_id},
            json={"request_id": request_id},
            timeout=self.timeout_seconds,
        )

    def _build_streaming_request(
        self,
        *,
        user_id: str,
        provider: str,
        model: str,
        query: str,
        conversation_id: str | None = None,
        headers: dict[str, str] | None = None,
        system_prompt: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        payload: dict[str, Any] = {"provider": provider, "model": model, "query": query}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if system_prompt:
            payload["system_prompt"] = system_prompt
        return payload, headers or {}

    def _open_streaming_query(
        self,
        *,
        user_id: str,
        provider: str,
        model: str,
        query: str,
        conversation_id: str | None = None,
        headers: dict[str, str] | None = None,
        system_prompt: str | None = None,
    ) -> requests.Response:
        payload, merged_headers = self._build_streaming_request(
            user_id=user_id,
            provider=provider,
            model=model,
            query=query,
            conversation_id=conversation_id,
            headers=headers,
            system_prompt=system_prompt,
        )
        return self.session.post(
            f"{self.base_url}/v1/streaming_query",
            params={"user_id": user_id},
            json=payload,
            headers=merged_headers,
            stream=True,
            timeout=self.timeout_seconds,
        )

    @staticmethod
    def _to_streaming_response(response: requests.Response, raw_lines: list[str]) -> StreamingResponse:
        return StreamingResponse(
            status_code=response.status_code,
            events=parse_sse_lines(raw_lines),
            raw_lines=raw_lines,
            headers=dict(response.headers),
        )

    def streaming_query(
        self,
        *,
        user_id: str,
        provider: str,
        model: str,
        query: str,
        conversation_id: str | None = None,
        headers: dict[str, str] | None = None,
        system_prompt: str | None = None,
    ) -> StreamingResponse:
        response = self._open_streaming_query(
            user_id=user_id,
            provider=provider,
            model=model,
            query=query,
            conversation_id=conversation_id,
            headers=headers,
            system_prompt=system_prompt,
        )
        raw_lines = [line for line in response.iter_lines(decode_unicode=True) if line]
        return self._to_streaming_response(response, raw_lines)

    def streaming_query_async(
        self,
        *,
        user_id: str,
        provider: str,
        model: str,
        query: str,
        conversation_id: str | None = None,
        headers: dict[str, str] | None = None,
        system_prompt: str | None = None,
    ) -> ActiveStream:
        """Start a streaming query and consume it on a background thread.

        Returns an ActiveStream whose partial_events can be inspected while the
        stream is still in progress, allowing interrupt calls mid-stream.
        """
        response = self._open_streaming_query(
            user_id=user_id,
            provider=provider,
            model=model,
            query=query,
            conversation_id=conversation_id,
            headers=headers,
            system_prompt=system_prompt,
        )

        stream = ActiveStream(response=response, _thread=threading.Thread(target=lambda: None))

        def _consume() -> None:
            try:
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        stream._raw_lines.append(line)
            finally:
                stream._done.set()

        thread = threading.Thread(target=_consume, daemon=True)
        stream._thread = thread
        thread.start()
        return stream

    @staticmethod
    def mcp_headers_value(header_payload: dict[str, Any]) -> str:
        return json.dumps(header_payload, separators=(",", ":"), sort_keys=True)

