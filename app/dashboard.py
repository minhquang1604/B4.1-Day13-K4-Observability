from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from . import logging_config
from .metrics import percentile


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DASHBOARD_CONFIG = REPO_ROOT / "config" / "dashboard.yaml"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_dashboard_config(path: Path = DEFAULT_DASHBOARD_CONFIG) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    dashboard = payload.get("dashboard") if isinstance(payload, dict) else None
    if not isinstance(dashboard, dict):
        raise ValueError("Dashboard config thiếu object 'dashboard'")
    return dashboard


def load_recent_log_records(
    log_path: Path,
    *,
    now: datetime,
    time_range_minutes: int,
) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []

    cutoff = now - timedelta(minutes=time_range_minutes)
    records: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        timestamp = _parse_timestamp(record.get("ts"))
        if timestamp is not None and cutoff <= timestamp <= now:
            records.append(record)
    return records


def _values(records: list[dict[str, Any]], event: str, field: str) -> list[float]:
    return [
        float(record[field])
        for record in records
        if record.get("event") == event and _is_number(record.get(field))
    ]


def _minute_series(
    records: list[dict[str, Any]],
    *,
    now: datetime,
    event: str,
    field: str | None = None,
    bucket_count: int = 12,
) -> list[dict[str, Any]]:
    end = now.replace(second=0, microsecond=0)
    buckets = [end - timedelta(minutes=index) for index in reversed(range(bucket_count))]
    totals: defaultdict[datetime, float] = defaultdict(float)

    for record in records:
        if record.get("event") != event:
            continue
        timestamp = _parse_timestamp(record.get("ts"))
        if timestamp is None:
            continue
        bucket = timestamp.replace(second=0, microsecond=0)
        if field is None:
            totals[bucket] += 1
        elif _is_number(record.get(field)):
            totals[bucket] += float(record[field])

    return [
        {"minute": bucket.strftime("%H:%M"), "value": totals[bucket]}
        for bucket in buckets
    ]


def build_dashboard_snapshot(
    *,
    log_path: Path | None = None,
    config_path: Path = DEFAULT_DASHBOARD_CONFIG,
    now: datetime | None = None,
) -> dict[str, Any]:
    dashboard = load_dashboard_config(config_path)
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    source_path = log_path or logging_config.LOG_PATH
    records = load_recent_log_records(
        source_path,
        now=current_time,
        time_range_minutes=dashboard["time_range_minutes"],
    )

    request_records = [record for record in records if record.get("event") == "request_received"]
    failed_records = [record for record in records if record.get("event") == "request_failed"]
    latencies = _values(records, "response_sent", "latency_ms")
    costs = _values(records, "response_sent", "cost_usd")
    tokens_in = _values(records, "response_sent", "tokens_in")
    tokens_out = _values(records, "response_sent", "tokens_out")
    quality_scores = _values(records, "response_sent", "quality_score")

    traffic_series = _minute_series(
        records, now=current_time, event="request_received"
    )
    cost_series = _minute_series(
        records, now=current_time, event="response_sent", field="cost_usd"
    )
    error_breakdown = Counter(
        str(record.get("error_type", "Unknown")) for record in failed_records
    )

    return {
        "title": dashboard["title"],
        "generated_at": current_time,
        "time_range_minutes": dashboard["time_range_minutes"],
        "refresh_seconds": dashboard["refresh_seconds"],
        "source": str(source_path).replace("\\", "/"),
        "record_count": len(records),
        "panel_config": {panel["id"]: panel for panel in dashboard["panels"]},
        "latency": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "sample_count": len(latencies),
        },
        "traffic": {
            "request_count": len(request_records),
            "peak_rpm": max((point["value"] for point in traffic_series), default=0),
            "series": traffic_series,
        },
        "errors": {
            "error_count": len(failed_records),
            "error_rate_pct": (
                round((len(failed_records) / len(request_records)) * 100, 2)
                if request_records
                else 0.0
            ),
            "breakdown": dict(sorted(error_breakdown.items())),
        },
        "cost": {
            "total": round(sum(costs), 6),
            "series": cost_series,
        },
        "tokens": {
            "input_total": int(sum(tokens_in)),
            "output_total": int(sum(tokens_out)),
        },
        "quality": {
            "average": round(sum(quality_scores) / len(quality_scores), 4)
            if quality_scores
            else 0.0,
            "sample_count": len(quality_scores),
        },
    }


def _threshold(snapshot: dict[str, Any], panel_id: str) -> dict[str, Any]:
    return snapshot["panel_config"][panel_id]["threshold"]


def _status(value: float, threshold: dict[str, Any], has_data: bool = True) -> tuple[str, str]:
    if not has_data:
        return "no-data", "No data"
    target = float(threshold["value"])
    healthy = value <= target if threshold["operator"] == "lte" else value >= target
    return ("healthy", "Within threshold") if healthy else ("breach", "Threshold breached")


def _format_number(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}"


def _bar(
    *,
    label: str,
    value: float,
    display_value: str,
    ceiling: float,
    threshold: float,
    series_class: str = "series-1",
) -> str:
    safe_ceiling = max(ceiling, 1e-9)
    width = min(100.0, max(0.0, value / safe_ceiling * 100))
    marker = min(100.0, max(0.0, threshold / safe_ceiling * 100))
    aria = html.escape(f"{label}: {display_value}", quote=True)
    return f"""
        <div class="metric-row">
          <div class="metric-label"><span>{html.escape(label)}</span><strong>{html.escape(display_value)}</strong></div>
          <div class="bar-track" role="img" aria-label="{aria}">
            <span class="bar-fill {series_class}" style="width:{width:.2f}%"></span>
            <span class="threshold-marker" style="left:{marker:.2f}%" aria-hidden="true"></span>
          </div>
        </div>"""


def _minute_bars(series: list[dict[str, Any]], unit: str, series_class: str) -> str:
    maximum = max((float(point["value"]) for point in series), default=0.0)
    bars = []
    for point in series:
        value = float(point["value"])
        height = 4 if maximum == 0 else max(4, round(value / maximum * 100))
        label = html.escape(
            f"{point['minute']}: {_format_number(value, 6 if unit == 'USD' else 0)} {unit}",
            quote=True,
        )
        bars.append(
            f'<span class="minute-bar {series_class}" style="height:{height}%" '
            f'aria-label="{label}"></span>'
        )
    return '<div class="minute-chart" role="group" aria-label="12-minute trend">' + "".join(bars) + "</div>"


def render_dashboard(snapshot: dict[str, Any]) -> str:
    latency = snapshot["latency"]
    traffic = snapshot["traffic"]
    errors = snapshot["errors"]
    cost = snapshot["cost"]
    tokens = snapshot["tokens"]
    quality = snapshot["quality"]

    latency_threshold = _threshold(snapshot, "latency")
    traffic_threshold = _threshold(snapshot, "traffic")
    error_threshold = _threshold(snapshot, "errors")
    cost_threshold = _threshold(snapshot, "cost")
    token_threshold = _threshold(snapshot, "tokens")
    quality_threshold = _threshold(snapshot, "quality")

    latency_ceiling = max(
        float(latency_threshold["value"]) * 1.25,
        float(latency["p99"]) * 1.1,
        1.0,
    )
    traffic_ceiling = max(
        float(traffic_threshold["value"]) * 1.25,
        float(traffic["peak_rpm"]) * 1.1,
        1.0,
    )
    error_ceiling = max(
        float(error_threshold["value"]) * 1.25,
        float(errors["error_rate_pct"]) * 1.1,
        1.0,
    )
    cost_ceiling = max(
        float(cost_threshold["value"]) * 1.25,
        float(cost["total"]) * 1.1,
        0.01,
    )
    token_value = max(tokens["input_total"], tokens["output_total"])
    token_ceiling = max(float(token_threshold["value"]) * 1.25, token_value * 1.1, 1.0)

    statuses = {
        "latency": _status(latency["p95"], latency_threshold, latency["sample_count"] > 0),
        "traffic": _status(traffic["peak_rpm"], traffic_threshold, traffic["request_count"] > 0),
        "errors": _status(errors["error_rate_pct"], error_threshold, traffic["request_count"] > 0),
        "cost": _status(cost["total"], cost_threshold, latency["sample_count"] > 0),
        "tokens": _status(token_value, token_threshold, latency["sample_count"] > 0),
        "quality": _status(quality["average"], quality_threshold, quality["sample_count"] > 0),
    }

    error_breakdown = "".join(
        f"<li><span>{html.escape(name)}</span><strong>{count}</strong></li>"
        for name, count in errors["breakdown"].items()
    ) or "<li><span>No errors in window</span><strong>0</strong></li>"

    panels = snapshot["panel_config"]
    generated_at = snapshot["generated_at"].strftime("%Y-%m-%d %H:%M:%S UTC")
    source = html.escape(snapshot["source"])

    def header(panel_id: str, value: str) -> str:
        css_class, label = statuses[panel_id]
        title = html.escape(panels[panel_id]["title"])
        unit = html.escape(str(panels[panel_id]["unit"]))
        return f"""
          <div class="panel-heading">
            <div><p class="eyebrow">{unit}</p><h2>{title}</h2></div>
            <span class="status {css_class}">{label}</span>
          </div>
          <p class="primary-value">{value}</p>"""

    latency_bars = "".join(
        _bar(
            label=label,
            value=float(latency[key]),
            display_value=f"{_format_number(latency[key])} ms",
            ceiling=latency_ceiling,
            threshold=float(latency_threshold["value"]),
            series_class=f"series-{index}",
        )
        for index, (key, label) in enumerate((("p50", "P50"), ("p95", "P95"), ("p99", "P99")), start=1)
    )

    token_bars = "".join(
        (
            _bar(
                label=label,
                value=float(value),
                display_value=_format_number(value),
                ceiling=token_ceiling,
                threshold=float(token_threshold["value"]),
                series_class=series_class,
            )
        )
        for label, value, series_class in (
            ("Input", tokens["input_total"], "series-1"),
            ("Output", tokens["output_total"], "series-2"),
        )
    )

    quality_bar = _bar(
        label="Mean quality",
        value=float(quality["average"]),
        display_value=f"{quality['average']:.2f}",
        ceiling=1.0,
        threshold=float(quality_threshold["value"]),
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(snapshot['title'])}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08111f;
      --surface: #0f1b2d;
      --surface-2: #14243a;
      --text: #f2f6fb;
      --muted: #9fb0c5;
      --border: #263a52;
      --good: #38d9a9;
      --bad: #ff6b7a;
      --empty: #8897aa;
      --series-1: #65b5ff;
      --series-2: #b69cff;
      --series-3: #4dd8c4;
      --threshold: #ffd166;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 28px; }}
    .topbar {{ display: flex; justify-content: space-between; gap: 24px; align-items: end; margin-bottom: 22px; }}
    h1, h2, p {{ margin: 0; }}
    h1 {{ font-size: clamp(24px, 3vw, 38px); font-weight: 650; letter-spacing: -0.03em; }}
    h2 {{ font-size: 17px; font-weight: 600; }}
    .subtitle, .meta, .panel-note {{ color: var(--muted); }}
    .subtitle {{ margin-top: 8px; }}
    .meta {{ text-align: right; font-size: 13px; line-height: 1.65; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
    .panel {{ background: linear-gradient(145deg, var(--surface), var(--surface-2)); border: 1px solid var(--border); border-radius: 16px; padding: 20px; min-height: 286px; }}
    .panel-heading {{ display: flex; justify-content: space-between; align-items: start; gap: 12px; }}
    .eyebrow {{ color: var(--muted); text-transform: uppercase; letter-spacing: .09em; font-size: 11px; margin-bottom: 5px; }}
    .status {{ border-radius: 999px; padding: 5px 9px; font-size: 11px; font-weight: 650; white-space: nowrap; border: 1px solid currentColor; }}
    .healthy {{ color: var(--good); }}
    .breach {{ color: var(--bad); }}
    .no-data {{ color: var(--empty); }}
    .primary-value {{ font-size: 34px; font-weight: 650; letter-spacing: -0.04em; margin: 24px 0 18px; }}
    .metric-row {{ margin-top: 14px; }}
    .metric-label {{ display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px; }}
    .metric-label span {{ color: var(--muted); }}
    .bar-track {{ position: relative; height: 9px; border-radius: 999px; background: rgba(159,176,197,.14); overflow: visible; }}
    .bar-fill {{ display: block; height: 100%; min-width: 2px; border-radius: inherit; }}
    .series-1 {{ background: var(--series-1); }}
    .series-2 {{ background: var(--series-2); }}
    .series-3 {{ background: var(--series-3); }}
    .threshold-marker {{ position: absolute; top: -4px; width: 2px; height: 17px; background: var(--threshold); border-radius: 2px; }}
    .threshold-note {{ display: flex; align-items: center; gap: 7px; margin-top: 13px; color: var(--muted); font-size: 11px; }}
    .threshold-key {{ width: 2px; height: 13px; background: var(--threshold); display: inline-block; }}
    .minute-chart {{ height: 82px; display: flex; align-items: end; gap: 5px; margin: 20px 0 12px; border-bottom: 1px solid var(--border); padding: 0 2px; }}
    .minute-bar {{ flex: 1; min-height: 4px; border-radius: 3px 3px 0 0; opacity: .9; }}
    .panel-note {{ font-size: 12px; line-height: 1.5; }}
    .breakdown {{ list-style: none; padding: 0; margin: 18px 0 0; display: grid; gap: 9px; }}
    .breakdown li {{ display: flex; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 8px; font-size: 12px; }}
    .breakdown span {{ color: var(--muted); }}
    footer {{ display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; color: var(--muted); font-size: 12px; margin-top: 18px; }}
    code {{ color: var(--text); }}
    @media (max-width: 1000px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    @media (max-width: 680px) {{
      main {{ padding: 18px; }}
      .topbar {{ align-items: start; flex-direction: column; }}
      .meta {{ text-align: left; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<main>
  <header class="topbar">
    <div>
      <h1>{html.escape(snapshot['title'])}</h1>
      <p class="subtitle">Operational view · Last {snapshot['time_range_minutes']} minutes</p>
    </div>
    <div class="meta">
      <div>Auto-refresh: {snapshot['refresh_seconds']}s</div>
      <div>Updated: {generated_at}</div>
    </div>
  </header>

  <section class="grid" aria-label="Six observability panels">
    <article class="panel" id="panel-latency" data-panel-id="latency">
      {header('latency', f"{_format_number(latency['p95'])} ms P95")}
      {latency_bars}
      <p class="threshold-note"><span class="threshold-key"></span>P95 ≤ {_format_number(latency_threshold['value'])} ms · {latency['sample_count']} samples</p>
    </article>

    <article class="panel" id="panel-traffic" data-panel-id="traffic">
      {header('traffic', f"{_format_number(traffic['request_count'])} requests")}
      {_minute_bars(traffic['series'], 'req/min', 'series-1')}
      <p class="panel-note">Peak {_format_number(traffic['peak_rpm'])} req/min · threshold ≥ {_format_number(traffic_threshold['value'])} req/min</p>
    </article>

    <article class="panel" id="panel-errors" data-panel-id="errors">
      {header('errors', f"{errors['error_rate_pct']:.2f}%")}
      {_bar(label='Error rate', value=float(errors['error_rate_pct']), display_value=f"{errors['error_rate_pct']:.2f}%", ceiling=error_ceiling, threshold=float(error_threshold['value']), series_class='series-3')}
      <ul class="breakdown" aria-label="Error breakdown">{error_breakdown}</ul>
      <p class="threshold-note"><span class="threshold-key"></span>Error rate ≤ {error_threshold['value']}%</p>
    </article>

    <article class="panel" id="panel-cost" data-panel-id="cost">
      {header('cost', f"${cost['total']:.4f}")}
      {_minute_bars(cost['series'], 'USD', 'series-2')}
      {_bar(label='Window total', value=float(cost['total']), display_value=f"${cost['total']:.4f}", ceiling=cost_ceiling, threshold=float(cost_threshold['value']), series_class='series-2')}
      <p class="threshold-note"><span class="threshold-key"></span>Total ≤ ${cost_threshold['value']}</p>
    </article>

    <article class="panel" id="panel-tokens" data-panel-id="tokens">
      {header('tokens', _format_number(tokens['input_total'] + tokens['output_total']))}
      {token_bars}
      <p class="threshold-note"><span class="threshold-key"></span>Per-field total ≤ {_format_number(token_threshold['value'])} tokens</p>
    </article>

    <article class="panel" id="panel-quality" data-panel-id="quality">
      {header('quality', f"{quality['average']:.2f} mean")}
      {quality_bar}
      <p class="threshold-note"><span class="threshold-key"></span>Mean ≥ {quality_threshold['value']:.2f} · {quality['sample_count']} samples</p>
    </article>
  </section>

  <footer>
    <span>Source: <code>{source}</code> · {snapshot['record_count']} records in window</span>
    <span>Yellow markers show dashboard thresholds</span>
  </footer>
</main>
<script>window.setTimeout(() => window.location.reload(), {snapshot['refresh_seconds'] * 1000});</script>
</body>
</html>"""


def render_current_dashboard() -> str:
    return render_dashboard(build_dashboard_snapshot())
