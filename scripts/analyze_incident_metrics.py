from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.challenge import ChallengeConfig, load_challenge
from app.cli import configure_utf8_stdio
from app.metrics import percentile


DEFAULT_LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"


class IncidentMetricsError(ValueError):
    pass


@dataclass(frozen=True)
class IncidentWindow:
    baseline_records: tuple[dict[str, Any], ...]
    incident_records: tuple[dict[str, Any], ...]
    enabled_at: str
    disabled_at: str | None


def load_log_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise IncidentMetricsError(f"Không tìm thấy log: {path}")

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    if not records:
        raise IncidentMetricsError("Log không có JSON record hợp lệ")
    return records


def _is_scenario_marker(record: dict[str, Any], event: str, scenario: str) -> bool:
    payload = record.get("payload")
    return (
        record.get("event") == event
        and isinstance(payload, dict)
        and payload.get("name") == scenario
    )


def find_latest_incident_window(
    records: list[dict[str, Any]], scenario: str
) -> IncidentWindow:
    enabled_indexes = [
        index
        for index, record in enumerate(records)
        if _is_scenario_marker(record, "incident_enabled", scenario)
    ]
    if not enabled_indexes:
        raise IncidentMetricsError(
            f"Không tìm thấy marker incident_enabled cho scenario '{scenario}'"
        )
    enabled_index = enabled_indexes[-1]

    disabled_index = next(
        (
            index
            for index in range(enabled_index + 1, len(records))
            if _is_scenario_marker(records[index], "incident_disabled", scenario)
        ),
        len(records),
    )
    app_start_index = max(
        (
            index
            for index in range(enabled_index)
            if records[index].get("event") == "app_started"
        ),
        default=-1,
    )

    enabled_at = str(records[enabled_index].get("ts", "unknown"))
    disabled_at = (
        str(records[disabled_index].get("ts", "unknown"))
        if disabled_index < len(records)
        else None
    )
    return IncidentWindow(
        baseline_records=tuple(records[app_start_index + 1 : enabled_index]),
        incident_records=tuple(records[enabled_index + 1 : disabled_index]),
        enabled_at=enabled_at,
        disabled_at=disabled_at,
    )


def _scope_feature(
    records: tuple[dict[str, Any], ...], affected_feature: str
) -> tuple[list[dict[str, Any]], str]:
    api_records = [record for record in records if record.get("service") == "api"]
    has_feature_metadata = any(record.get("feature") is not None for record in api_records)
    if has_feature_metadata:
        return (
            [record for record in api_records if record.get("feature") == affected_feature],
            "feature_metadata",
        )
    return api_records, "phase_only"


def _numeric_values(
    records: list[dict[str, Any]], event: str, field: str
) -> list[float]:
    values: list[float] = []
    for record in records:
        value = record.get(field)
        if record.get("event") == event and isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def calculate_phase_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = _numeric_values(records, "response_sent", "latency_ms")
    costs = _numeric_values(records, "response_sent", "cost_usd")
    tokens_in = _numeric_values(records, "response_sent", "tokens_in")
    tokens_out = _numeric_values(records, "response_sent", "tokens_out")
    quality_scores = _numeric_values(records, "response_sent", "quality_score")
    request_count = sum(record.get("event") == "request_received" for record in records)
    error_count = sum(record.get("event") == "request_failed" for record in records)
    response_timestamps = [
        str(record["ts"])
        for record in records
        if record.get("event") == "response_sent" and record.get("ts")
    ]

    return {
        "request_count": request_count,
        "response_count": len(latencies),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "latency_p99_ms": percentile(latencies, 99),
        "error_count": error_count,
        "error_rate_pct": round(error_count / request_count * 100, 2)
        if request_count
        else 0.0,
        "total_cost_usd": round(sum(costs), 6),
        "tokens_in_total": int(sum(tokens_in)),
        "tokens_out_total": int(sum(tokens_out)),
        "quality_avg": round(sum(quality_scores) / len(quality_scores), 4)
        if quality_scores
        else 0.0,
        "first_response_at": min(response_timestamps) if response_timestamps else None,
        "last_response_at": max(response_timestamps) if response_timestamps else None,
    }


def analyze_incident(
    records: list[dict[str, Any]], challenge: ChallengeConfig
) -> dict[str, Any]:
    window = find_latest_incident_window(records, challenge.incident)
    baseline_records, baseline_scope = _scope_feature(
        window.baseline_records, challenge.affected_feature
    )
    incident_records, incident_scope = _scope_feature(
        window.incident_records, challenge.affected_feature
    )
    baseline = calculate_phase_metrics(baseline_records)
    incident = calculate_phase_metrics(incident_records)

    if baseline["response_count"] == 0:
        raise IncidentMetricsError("Pha baseline không có response_sent để so sánh")
    if incident["response_count"] == 0:
        raise IncidentMetricsError("Pha incident không có response_sent để so sánh")

    baseline_p95 = float(baseline["latency_p95_ms"])
    incident_p95 = float(incident["latency_p95_ms"])
    threshold = float(challenge.latency_threshold_ms)
    delta_ms = incident_p95 - baseline_p95
    multiplier = incident_p95 / baseline_p95 if baseline_p95 else None
    threshold_breached = incident_p95 > threshold

    if threshold_breached and delta_ms > 0:
        symptom = "Tail latency regression"
    elif delta_ms > 0:
        symptom = "Latency increased but stayed below challenge threshold"
    else:
        symptom = "No latency regression detected"

    return {
        "challenge_id": challenge.challenge_id,
        "scenario": challenge.incident,
        "affected_feature": challenge.affected_feature,
        "latency_threshold_ms": challenge.latency_threshold_ms,
        "feature_scope": (
            "feature_metadata"
            if baseline_scope == incident_scope == "feature_metadata"
            else "phase_only"
        ),
        "incident_enabled_at": window.enabled_at,
        "incident_disabled_at": window.disabled_at,
        "baseline": baseline,
        "incident": incident,
        "comparison": {
            "p95_delta_ms": round(delta_ms, 2),
            "p95_multiplier": round(multiplier, 2) if multiplier is not None else None,
            "threshold_breached": threshold_breached,
            "symptom": symptom,
        },
    }


def render_report(analysis: dict[str, Any]) -> str:
    baseline = analysis["baseline"]
    incident = analysis["incident"]
    comparison = analysis["comparison"]
    multiplier = (
        f"{comparison['p95_multiplier']:.2f}x"
        if comparison["p95_multiplier"] is not None
        else "n/a"
    )
    scope_note = (
        f"feature metadata ({analysis['affected_feature']})"
        if analysis["feature_scope"] == "feature_metadata"
        else "incident phase markers (feature metadata unavailable)"
    )

    return "\n".join(
        [
            "CP3 METRICS EVIDENCE",
            f"Challenge: {analysis['challenge_id']}",
            f"Scenario: {analysis['scenario']}",
            f"Affected feature: {analysis['affected_feature']}",
            f"Scope: {scope_note}",
            "",
            "BASELINE",
            f"- Requests/responses: {baseline['request_count']}/{baseline['response_count']}",
            f"- Latency P50/P95/P99: {baseline['latency_p50_ms']:.0f}/{baseline['latency_p95_ms']:.0f}/{baseline['latency_p99_ms']:.0f} ms",
            f"- Error rate: {baseline['error_rate_pct']:.2f}%",
            f"- Cost: ${baseline['total_cost_usd']:.6f}",
            "",
            "INCIDENT",
            f"- Requests/responses: {incident['request_count']}/{incident['response_count']}",
            f"- Latency P50/P95/P99: {incident['latency_p50_ms']:.0f}/{incident['latency_p95_ms']:.0f}/{incident['latency_p99_ms']:.0f} ms",
            f"- Error rate: {incident['error_rate_pct']:.2f}%",
            f"- Cost: ${incident['total_cost_usd']:.6f}",
            "",
            "COMPARISON",
            f"- P95 delta: +{comparison['p95_delta_ms']:.0f} ms ({multiplier})",
            f"- Challenge threshold: {analysis['latency_threshold_ms']} ms",
            f"- Threshold breached: {str(comparison['threshold_breached']).lower()}",
            f"- Symptom: {comparison['symptom']}",
            f"- Incident marker: {analysis['incident_enabled_at']}",
            f"- First affected response: {incident['first_response_at']}",
            f"- Last affected response: {incident['last_response_at']}",
            f"- Incident disabled: {analysis['incident_disabled_at']}",
            "",
            "BOUNDARY",
            "Metrics establish the symptom and affected time window only. Use traces to localize the abnormal span and logs to prove root cause.",
        ]
    )


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="So sánh metrics baseline và incident chính thức của CP3"
    )
    parser.add_argument("--logs", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument(
        "--challenge",
        type=Path,
        default=REPO_ROOT / "config" / "challenge.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        challenge = load_challenge(args.challenge)
        analysis = analyze_incident(load_log_records(args.logs), challenge)
    except (IncidentMetricsError, FileNotFoundError, ValueError) as exc:
        print(f"KHÔNG THỂ PHÂN TÍCH: {exc}")
        return 1

    report = render_report(analysis)
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
        print(f"\nEvidence saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
