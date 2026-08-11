# CP4 — Rà soát dashboard cuối

Checkpoint cuối của vai trò Metrics/Dashboard được kiểm tra trên bản tích hợp
`origin/main` tại commit `78805cf`. Ba commit CP1–CP3 của vai trò này đều là
ancestor của commit trên, nên dashboard cuối bao gồm cả phần Logging/PII/Tracing
và SRE đã merge từ các thành viên khác.

## Kết quả kiểm chứng tích hợp

| Kiểm tra | Kết quả |
|---|---|
| Full test suite | 43 passed |
| Dashboard validator | 6/6 panel, 7/7 field trong logging schema |
| Log validator | 100/100 |
| Correlation ID | 12 ID duy nhất trong lượt chạy cuối |
| Missing enrichment | 0 |
| PII leak | 0 |

Lượt chạy cuối dùng cùng 5 input challenge cho baseline và incident. Sau khi phần
Logging được merge, báo cáo metrics scope trực tiếp theo `feature=monitoring`:

- Baseline P95: 151 ms.
- Incident P95: 2.651 ms.
- Delta: +2.500 ms, khoảng 17,56 lần.
- Error rate: 0% ở cả hai pha.
- Challenge threshold 2.000 ms: breached.

## Checklist ảnh dashboard cuối

- Đúng 6 panel: latency, traffic, errors, cost, tokens và quality.
- Tên panel, đơn vị và giá trị chính đều đọc được.
- Cửa sổ mặc định 60 phút và auto-refresh 30 giây hiển thị ở header.
- Threshold marker màu vàng xuất hiện trên các panel.
- Ảnh 1440×1080 không có panel bị cắt hoặc chồng chữ.
- Nguồn `data/logs.jsonl` và số record trong cửa sổ hiển thị ở footer.

Dashboard contract dùng ngưỡng vận hành P95 3.000 ms, trong khi challenge dùng
ngưỡng điều tra 2.000 ms. Badge `Within threshold` trong ảnh tuân theo dashboard
contract; kết luận incident breached dựa trên challenge contract.

## Evidence cuối

- `submission/evidence/dashboard-final.png`: screenshot dashboard từ bản tích hợp.
- `submission/evidence/cp4-final-metrics-analysis.txt`: baseline/incident, feature
  scope và khoảng thời gian ảnh hưởng từ lượt chạy cuối.

Các lệnh kiểm tra có thể chạy lại:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\validate_dashboard.py
.\.venv\Scripts\python.exe scripts\validate_logs.py
.\.venv\Scripts\python.exe scripts\analyze_incident_metrics.py
```

