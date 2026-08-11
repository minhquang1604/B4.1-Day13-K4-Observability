from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.main import app
from app.middleware import REQUEST_ID_HEADER, RESPONSE_TIME_HEADER, resolve_correlation_id

CORRELATION_ID_FORMAT = re.compile(r"^req-[0-9a-f]{8}$")
ENRICHMENT_FIELDS = {"user_id_hash", "session_id", "feature", "model", "env"}


def chat_payload(user_id: str = "student-01", session_id: str = "session-01") -> dict:
    return {
        "user_id": user_id,
        "session_id": session_id,
        "feature": "qa",
        "message": "Explain observability",
    }


def read_events(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]


def test_generated_correlation_id_is_returned_in_headers_and_body(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    with TestClient(app) as client:
        response = client.post("/chat", json=chat_payload())

    assert response.status_code == 200
    correlation_id = response.headers[REQUEST_ID_HEADER]
    assert CORRELATION_ID_FORMAT.match(correlation_id)
    assert response.json()["correlation_id"] == correlation_id
    assert float(response.headers[RESPONSE_TIME_HEADER]) > 0


def test_valid_inbound_request_id_is_reused(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.post(
            "/chat", json=chat_payload(), headers={REQUEST_ID_HEADER: "req-deadbeef"}
        )

    assert response.headers[REQUEST_ID_HEADER] == "req-deadbeef"
    api_events = [event for event in read_events(log_path) if event.get("service") == "api"]
    assert api_events
    assert all(event["correlation_id"] == "req-deadbeef" for event in api_events)


def test_malformed_inbound_request_id_is_replaced() -> None:
    poisoned = 'req-<script>\n{"event": "fake_admin_login"}'
    assert resolve_correlation_id(poisoned) != poisoned
    assert CORRELATION_ID_FORMAT.match(resolve_correlation_id(poisoned))
    assert CORRELATION_ID_FORMAT.match(resolve_correlation_id(None))
    assert CORRELATION_ID_FORMAT.match(resolve_correlation_id("REQ-DEADBEEF"))


def test_context_does_not_leak_between_requests(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        first = client.post("/chat", json=chat_payload("user-a", "session-a"))
        second = client.post("/chat", json=chat_payload("user-b", "session-b"))

    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]

    api_events = [event for event in read_events(log_path) if event.get("service") == "api"]
    sessions_by_id = {event["correlation_id"]: event["session_id"] for event in api_events}
    assert sessions_by_id[first.headers[REQUEST_ID_HEADER]] == "session-a"
    assert sessions_by_id[second.headers[REQUEST_ID_HEADER]] == "session-b"


def test_api_logs_carry_correlation_id_and_enrichment(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.post("/chat", json=chat_payload())

    api_events = [event for event in read_events(log_path) if event.get("service") == "api"]
    assert {event["event"] for event in api_events} == {"request_received", "response_sent"}
    for event in api_events:
        assert event["correlation_id"] == response.headers[REQUEST_ID_HEADER]
        assert ENRICHMENT_FIELDS.issubset(event.keys())
        assert event["user_id_hash"] != "student-01"
