from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

from app import logging_config
from app.agent import AgentResult
from app.main import agent, app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _successful_result(*args, **kwargs) -> AgentResult:
    return AgentResult(
        answer="A dashboard-contract test response.",
        latency_ms=125,
        tokens_in=40,
        tokens_out=80,
        cost_usd=0.00132,
        quality_score=0.8,
    )


def _failed_result(*args, **kwargs) -> AgentResult:
    raise RuntimeError("synthetic dashboard-contract failure")


def test_runtime_logs_supply_events_and_fields_for_all_six_panels(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    request_body = {
        "user_id": "dashboard-audit-user",
        "session_id": "dashboard-audit-session",
        "feature": "monitoring",
        "message": "Verify the dashboard log contract",
    }

    with TestClient(app, raise_server_exceptions=False) as client:
        monkeypatch.setattr(agent, "run", _successful_result)
        assert client.post("/chat", json=request_body).status_code == 200

        monkeypatch.setattr(agent, "run", _failed_result)
        assert client.post("/chat", json=request_body).status_code == 500

    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dashboard = yaml.safe_load(
        (REPO_ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8")
    )["dashboard"]

    for panel in dashboard["panels"]:
        panel_id = panel["id"]
        for event_name in panel["events"]:
            assert any(record.get("event") == event_name for record in records), (
                f"{panel_id}: missing event {event_name}"
            )

        matching_records = [
            record for record in records if record.get("event") in panel["events"]
        ]
        for field in panel["fields"]:
            assert any(field in record for record in matching_records), (
                f"{panel_id}: no configured event supplies field {field}"
            )
