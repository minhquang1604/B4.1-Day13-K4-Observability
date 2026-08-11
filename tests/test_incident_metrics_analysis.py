from __future__ import annotations

from app.challenge import ChallengeConfig
from scripts.analyze_incident_metrics import (
    IncidentMetricsError,
    analyze_incident,
    render_report,
)


def _record(ts: str, event: str, **fields) -> dict:
    return {
        "ts": ts,
        "event": event,
        "service": fields.pop("service", "api"),
        **fields,
    }


def _response(ts: str, latency_ms: int) -> dict:
    return _record(
        ts,
        "response_sent",
        feature="monitoring",
        latency_ms=latency_ms,
        cost_usd=0.001,
        tokens_in=20,
        tokens_out=40,
        quality_score=0.8,
    )


def _challenge() -> ChallengeConfig:
    return ChallengeConfig(
        cohort="K4",
        challenge_id="day13-k4-test",
        incident="rag_slow",
        seed=1304,
        affected_feature="monitoring",
        latency_threshold_ms=2000,
        queries=(),
    )


def test_analysis_compares_baseline_and_latest_incident_window() -> None:
    records = [
        _record("2026-08-11T08:00:00Z", "app_started", service="lab"),
        _record("2026-08-11T08:00:01Z", "request_received", feature="monitoring"),
        _response("2026-08-11T08:00:02Z", 150),
        _record(
            "2026-08-11T08:01:00Z",
            "incident_enabled",
            service="control",
            payload={"name": "rag_slow"},
        ),
        _record("2026-08-11T08:01:01Z", "request_received", feature="monitoring"),
        _response("2026-08-11T08:01:04Z", 2650),
        _record(
            "2026-08-11T08:01:05Z",
            "incident_disabled",
            service="control",
            payload={"name": "rag_slow"},
        ),
    ]

    analysis = analyze_incident(records, _challenge())

    assert analysis["baseline"]["latency_p95_ms"] == 150
    assert analysis["incident"]["latency_p95_ms"] == 2650
    assert analysis["comparison"] == {
        "p95_delta_ms": 2500.0,
        "p95_multiplier": 17.67,
        "threshold_breached": True,
        "symptom": "Tail latency regression",
    }
    assert analysis["feature_scope"] == "feature_metadata"
    assert "Metrics establish the symptom" in render_report(analysis)


def test_analysis_falls_back_to_phase_scope_without_feature_metadata() -> None:
    records = [
        _record("2026-08-11T08:00:00Z", "app_started", service="lab"),
        _record("2026-08-11T08:00:01Z", "request_received"),
        {**_response("2026-08-11T08:00:02Z", 150), "feature": None},
        _record(
            "2026-08-11T08:01:00Z",
            "incident_enabled",
            service="control",
            payload={"name": "rag_slow"},
        ),
        _record("2026-08-11T08:01:01Z", "request_received"),
        {**_response("2026-08-11T08:01:04Z", 2650), "feature": None},
    ]

    analysis = analyze_incident(records, _challenge())

    assert analysis["feature_scope"] == "phase_only"
    assert analysis["comparison"]["threshold_breached"] is True


def test_analysis_requires_an_incident_marker() -> None:
    try:
        analyze_incident([_record("2026-08-11T08:00:00Z", "app_started")], _challenge())
    except IncidentMetricsError as exc:
        assert "incident_enabled" in str(exc)
    else:
        raise AssertionError("Expected IncidentMetricsError")
