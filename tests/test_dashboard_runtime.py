from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.dashboard import build_dashboard_snapshot, render_dashboard
from app.main import app


def _write_records(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\nnot-json\n",
        encoding="utf-8",
    )


def _record(timestamp: datetime, event: str, **fields) -> dict:
    return {
        "ts": timestamp.isoformat().replace("+00:00", "Z"),
        "level": "info",
        "service": "api",
        "event": event,
        **fields,
    }


def test_snapshot_calculates_all_six_panels_from_recent_jsonl(tmp_path: Path) -> None:
    now = datetime(2026, 8, 11, 8, 30, tzinfo=timezone.utc)
    log_path = tmp_path / "logs.jsonl"
    records = [
        _record(now - timedelta(minutes=3), "request_received"),
        _record(
            now - timedelta(minutes=3),
            "response_sent",
            latency_ms=100,
            cost_usd=0.01,
            tokens_in=10,
            tokens_out=20,
            quality_score=0.7,
        ),
        _record(now - timedelta(minutes=2), "request_received"),
        _record(
            now - timedelta(minutes=2),
            "response_sent",
            latency_ms=200,
            cost_usd=0.02,
            tokens_in=20,
            tokens_out=30,
            quality_score=0.8,
        ),
        _record(now - timedelta(minutes=1), "request_received"),
        _record(now - timedelta(minutes=1), "request_failed", error_type="RuntimeError"),
        _record(
            now - timedelta(minutes=1),
            "response_sent",
            latency_ms=400,
            cost_usd=0.03,
            tokens_in=30,
            tokens_out=40,
            quality_score=0.9,
        ),
        _record(now - timedelta(minutes=61), "request_received"),
    ]
    _write_records(log_path, records)

    snapshot = build_dashboard_snapshot(log_path=log_path, now=now)

    assert snapshot["record_count"] == 7
    assert snapshot["latency"] == {
        "p50": 200.0,
        "p95": 400.0,
        "p99": 400.0,
        "sample_count": 3,
    }
    assert snapshot["traffic"]["request_count"] == 3
    assert snapshot["traffic"]["peak_rpm"] == 1
    assert snapshot["errors"] == {
        "error_count": 1,
        "error_rate_pct": 33.33,
        "breakdown": {"RuntimeError": 1},
    }
    assert snapshot["cost"]["total"] == 0.06
    assert snapshot["tokens"] == {"input_total": 60, "output_total": 90}
    assert snapshot["quality"] == {"average": 0.8, "sample_count": 3}


def test_rendered_dashboard_has_six_panels_units_thresholds_and_refresh(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 8, 11, 8, 30, tzinfo=timezone.utc)
    log_path = tmp_path / "logs.jsonl"
    _write_records(
        log_path,
        [
            _record(now, "request_received"),
            _record(
                now,
                "response_sent",
                latency_ms=150,
                cost_usd=0.001,
                tokens_in=25,
                tokens_out=50,
                quality_score=0.8,
            ),
        ],
    )

    rendered = render_dashboard(build_dashboard_snapshot(log_path=log_path, now=now))

    assert rendered.count('data-panel-id="') == 6
    for panel_id in ("latency", "traffic", "errors", "cost", "tokens", "quality"):
        assert f'data-panel-id="{panel_id}"' in rendered
    assert "Last 60 minutes" in rendered
    assert "Auto-refresh: 30s" in rendered
    assert "Yellow markers show dashboard thresholds" in rendered
    assert "window.location.reload()" in rendered


def test_dashboard_route_returns_runtime_html(monkeypatch, tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    log_path = tmp_path / "logs.jsonl"
    _write_records(
        log_path,
        [
            _record(now, "request_received"),
            _record(
                now,
                "response_sent",
                latency_ms=175,
                cost_usd=0.001,
                tokens_in=30,
                tokens_out=60,
                quality_score=0.8,
            ),
        ],
    )
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text.count('data-panel-id="') == 6
