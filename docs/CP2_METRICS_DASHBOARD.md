# CP2 — Metrics và dashboard 6 panel

Phạm vi của vai trò Dashboard ở checkpoint 2 là biến structured log thành một
dashboard runtime có thể kiểm chứng. SLO, alert rules và runbook thuộc vai trò
SRE/Alerts nên không được thay đổi trong phần này.

## Pipeline dữ liệu

`GET /dashboard` đọc trực tiếp `data/logs.jsonl`, chỉ giữ record trong 60 phút gần
nhất và tính các chỉ số theo `config/dashboard.yaml`:

| Panel | Phép tính runtime |
|---|---|
| Latency | P50/P95/P99 của `response_sent.latency_ms` |
| Traffic | số `request_received` và request/phút |
| Errors | `request_failed / request_received * 100` và count theo `error_type` |
| Cost | tổng `response_sent.cost_usd` theo phút và toàn cửa sổ |
| Tokens | tổng riêng `tokens_in` và `tokens_out` |
| Quality | mean của `response_sent.quality_score` |

Dashboard hiển thị đúng sáu panel, đơn vị, threshold marker, cửa sổ 60 phút và tự
refresh sau 30 giây. Record JSON lỗi hoặc nằm ngoài cửa sổ thời gian được bỏ qua.

## Cách chạy và kiểm chứng

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
.\.venv\Scripts\python.exe scripts\load_test.py --concurrency 5
.\.venv\Scripts\python.exe scripts\validate_dashboard.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_dashboard_runtime.py
```

Mở `http://127.0.0.1:8000/dashboard` để kiểm tra dashboard runtime.

## Evidence CP2

- Dashboard runtime: `submission/evidence/dashboard-cp2.png`
- Validator mong đợi: `HỢP LỆ: 6/6 panel ...; 7/7 field ...`
- Test runtime kiểm tra phép tính, cấu trúc sáu panel và HTTP response của route.

