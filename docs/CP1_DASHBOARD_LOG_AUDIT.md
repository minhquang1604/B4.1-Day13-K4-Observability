# CP1 — Đối chiếu log với 6 panel dashboard

Phạm vi của checkpoint này là xác nhận structured log cung cấp đủ event/field cho
dashboard. Việc hoàn thiện correlation ID, metadata và PII redaction thuộc vai trò
Logging & PII; dựng biểu đồ, SLO và alert được thực hiện ở CP2.

## Ma trận log → panel

| Panel | Event nguồn | Field bắt buộc | Nơi phát log | Kết quả CP1 |
|---|---|---|---|---|
| Latency | `response_sent` | `latency_ms` | `app/main.py` | Đủ |
| Traffic | `request_received` | `event` (đếm request) | `app/main.py` | Đủ |
| Errors | `request_received`, `request_failed` | `event`, `error_type` | `app/main.py` | Đủ |
| Cost | `response_sent` | `cost_usd` | `app/main.py` | Đủ |
| Tokens | `response_sent` | `tokens_in`, `tokens_out` | `app/main.py` | Đủ |
| Quality | `response_sent` | `quality_score` | `app/main.py` | Đủ |

`scripts/validate_dashboard.py` kiểm tra thêm rằng mọi field được dashboard khai báo
đều tồn tại trong `config/logging_schema.json`. Test runtime tạo cả request thành công
và thất bại để chứng minh các event/field trong bảng thực sự được ghi ra JSONL.

## Cách kiểm chứng CP1

```powershell
.\.venv\Scripts\python.exe scripts\validate_dashboard.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_dashboard_log_contract.py tests/test_dashboard_validator.py
```

Kết quả mong đợi:

- validator báo `6/6 panel` và toàn bộ dashboard field có trong logging schema;
- test runtime chứng minh đủ nguồn dữ liệu cho cả sáu panel;
- chưa yêu cầu screenshot dashboard ở CP1.

