from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app import agent as agent_module
from app import logging_config
from app.main import app
from app.middleware import REQUEST_ID_HEADER
from app.tracing import current_trace_id


class RecordingClient:
    """Stands in for the Langfuse client so the link is testable without keys."""

    def __init__(self, trace_id: str | None = "trace-abc123") -> None:
        self.trace_id = trace_id
        self.trace_updates: list[dict[str, Any]] = []
        self.generation_updates: list[dict[str, Any]] = []

    def update_current_trace(self, **kwargs: Any) -> None:
        self.trace_updates.append(kwargs)

    def update_current_generation(self, **kwargs: Any) -> None:
        self.generation_updates.append(kwargs)

    def get_current_trace_id(self) -> str | None:
        return self.trace_id

    def get_prompt(self, *args: Any, **kwargs: Any):  # pragma: no cover - tracing disabled
        raise AssertionError("prompt fetch is not part of this test")


def chat_payload() -> dict:
    return {
        "user_id": "student-01",
        "session_id": "session-01",
        "feature": "qa",
        "message": "Explain observability",
    }


def test_generation_metadata_carries_the_request_correlation_id(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")
    recorder = RecordingClient()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: recorder)

    with TestClient(app) as client:
        response = client.post(
            "/chat", json=chat_payload(), headers={REQUEST_ID_HEADER: "req-deadbeef"}
        )

    assert response.status_code == 200
    assert recorder.generation_updates[0]["metadata"]["correlation_id"] == "req-deadbeef"
    # Trace metadata stays pinned to the prompt keys asserted by the public
    # test_agent_prompt_trace contract.
    assert "correlation_id" not in recorder.trace_updates[0]["metadata"]


def test_response_log_carries_the_trace_id(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: RecordingClient())

    with TestClient(app) as client:
        response = client.post("/chat", json=chat_payload())

    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["trace_id"] == "trace-abc123"
    assert response_event["correlation_id"] == response.headers[REQUEST_ID_HEADER]


def test_request_survives_when_trace_id_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    class BrokenClient(RecordingClient):
        def get_current_trace_id(self) -> str | None:
            raise RuntimeError("langfuse unreachable")

    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: BrokenClient())

    with TestClient(app) as client:
        response = client.post("/chat", json=chat_payload())

    assert response.status_code == 200
    assert current_trace_id(object()) is None
