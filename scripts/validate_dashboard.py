from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio


DEFAULT_LOGGING_SCHEMA = REPO_ROOT / "config" / "logging_schema.json"
REQUIRED_PANEL_IDS = frozenset(
    {"latency", "traffic", "errors", "cost", "tokens", "quality"}
)
REQUIRED_PANEL_FIELDS = (
    "title",
    "source",
    "events",
    "fields",
    "aggregations",
    "query",
    "unit",
    "threshold",
)


class DashboardConfigError(ValueError):
    pass


def load_logging_schema(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DashboardConfigError(f"Không tìm thấy logging schema: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DashboardConfigError(
            f"Logging schema không phải JSON hợp lệ: {exc}"
        ) from exc

    properties = payload.get("properties") if isinstance(payload, dict) else None
    if not isinstance(properties, dict):
        raise DashboardConfigError("Logging schema thiếu object 'properties'")
    return payload


def validate_log_field_contract(dashboard: dict, logging_schema: dict) -> None:
    """Ensure every field used by a dashboard panel is part of the log schema."""
    schema_fields = set(logging_schema["properties"])
    missing_by_panel: dict[str, list[str]] = {}

    for panel in dashboard["panels"]:
        missing = sorted(set(panel["fields"]) - schema_fields)
        if missing:
            missing_by_panel[panel["id"]] = missing

    if missing_by_panel:
        details = "; ".join(
            f"{panel_id}: {', '.join(fields)}"
            for panel_id, fields in sorted(missing_by_panel.items())
        )
        raise DashboardConfigError(
            f"Dashboard dùng field chưa có trong logging schema: {details}"
        )


def load_dashboard_config(
    path: Path,
    logging_schema_path: Path = DEFAULT_LOGGING_SCHEMA,
) -> dict:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DashboardConfigError(f"Không tìm thấy dashboard config: {path}") from exc
    except yaml.YAMLError as exc:
        raise DashboardConfigError(f"Dashboard config không phải YAML hợp lệ: {exc}") from exc

    dashboard = payload.get("dashboard") if isinstance(payload, dict) else None
    if not isinstance(dashboard, dict):
        raise DashboardConfigError("Thiếu object 'dashboard'")
    if dashboard.get("schema_version") != 1:
        raise DashboardConfigError("'dashboard.schema_version' phải bằng 1")
    if dashboard.get("time_range_minutes") != 60:
        raise DashboardConfigError("'dashboard.time_range_minutes' phải bằng 60")
    refresh_seconds = dashboard.get("refresh_seconds")
    if not isinstance(refresh_seconds, int) or not 15 <= refresh_seconds <= 30:
        raise DashboardConfigError("'dashboard.refresh_seconds' phải nằm trong khoảng 15–30")

    panels = dashboard.get("panels")
    if not isinstance(panels, list) or len(panels) != 6:
        raise DashboardConfigError("Dashboard phải có đúng 6 panel")
    panel_ids = {
        panel.get("id") for panel in panels if isinstance(panel, dict) and panel.get("id")
    }
    if panel_ids != REQUIRED_PANEL_IDS:
        missing = ", ".join(sorted(REQUIRED_PANEL_IDS - panel_ids)) or "không"
        extra = ", ".join(sorted(panel_ids - REQUIRED_PANEL_IDS)) or "không"
        raise DashboardConfigError(
            f"Panel ID không đúng; thiếu: {missing}; không hỗ trợ: {extra}"
        )

    for panel in panels:
        if not isinstance(panel, dict):
            raise DashboardConfigError("Mỗi dashboard panel phải là một YAML object")
        panel_id = panel["id"]
        for field in REQUIRED_PANEL_FIELDS:
            if panel.get(field) in (None, "", []):
                raise DashboardConfigError(f"Thiếu hoặc rỗng: {panel_id}.{field}")
        if not all(isinstance(panel[field], list) for field in ("events", "fields", "aggregations")):
            raise DashboardConfigError(
                f"'{panel_id}.events/fields/aggregations' phải là danh sách"
            )

        threshold = panel["threshold"]
        if not isinstance(threshold, dict):
            raise DashboardConfigError(f"'{panel_id}.threshold' phải là một YAML object")
        if threshold.get("aggregation") not in panel["aggregations"]:
            raise DashboardConfigError(
                f"'{panel_id}.threshold.aggregation' phải thuộc aggregations của panel"
            )
        if threshold.get("operator") not in {"lte", "gte"}:
            raise DashboardConfigError(
                f"'{panel_id}.threshold.operator' chỉ nhận 'lte' hoặc 'gte'"
            )
        if not isinstance(threshold.get("value"), (int, float)):
            raise DashboardConfigError(f"'{panel_id}.threshold.value' phải là một số")

    logging_schema = load_logging_schema(logging_schema_path)
    validate_log_field_contract(dashboard, logging_schema)
    return payload


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Kiểm tra dashboard contract của Day 13")
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "config" / "dashboard.yaml",
        help="Đường dẫn tới dashboard YAML",
    )
    parser.add_argument(
        "--logging-schema",
        type=Path,
        default=DEFAULT_LOGGING_SCHEMA,
        help="Đường dẫn tới JSON schema của structured log",
    )
    args = parser.parse_args()

    try:
        payload = load_dashboard_config(args.config, args.logging_schema)
    except DashboardConfigError as exc:
        print(f"KHÔNG HỢP LỆ: {exc}")
        return 1

    dashboard_fields = {
        field
        for panel in payload["dashboard"]["panels"]
        for field in panel["fields"]
    }
    print(
        f"HỢP LỆ: {len(REQUIRED_PANEL_IDS)}/6 panel có trong dashboard contract; "
        f"{len(dashboard_fields)}/{len(dashboard_fields)} field có trong logging schema."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
