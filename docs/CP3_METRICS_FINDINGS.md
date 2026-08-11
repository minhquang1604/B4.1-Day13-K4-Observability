# CP3 — Triệu chứng từ metrics

Phần này chỉ kết luận triệu chứng và khoảng thời gian ảnh hưởng từ metrics. Span
bất thường và root cause phải được xác nhận độc lập bởi thành viên Tracing và
Logging.

## Cách chạy

Challenge chính thức được chạy hai lần với cùng 5 input và concurrency 5:

1. Baseline khi incident tắt.
2. Bật incident bằng `python scripts/inject_incident.py`.
3. Chạy lại `python scripts/load_test.py --challenge --concurrency 5`.
4. Tắt incident bằng `python scripts/inject_incident.py --disable`.
5. Phân tích bằng:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_incident_metrics.py `
  --output submission\evidence\cp3-metrics-analysis.txt
```

Script dùng cặp marker `incident_enabled`/`incident_disabled` gần nhất để tách pha,
không hard-code timestamp hoặc kết quả challenge.

## Kết quả chính thức

| Metric | Baseline | Incident | Diễn giải |
|---|---:|---:|---|
| Request/response | 5/5 | 5/5 | Hai pha có cùng cỡ mẫu |
| Latency P50 | 150 ms | 2.651 ms | Toàn bộ phân phối dịch lên |
| Latency P95 | 151 ms | 2.651 ms | Tăng 2.500 ms, khoảng 17,56 lần |
| Latency P99 | 151 ms | 2.651 ms | Tail latency tăng rõ |
| Error rate | 0% | 0% | Không phải triệu chứng availability |

Ngưỡng chính thức trong `config/challenge.json` là 2.000 ms. P95 incident đạt
2.651 ms nên kết luận từ metrics là **tail-latency regression** trên luồng
`monitoring`.

Khoảng thời gian ảnh hưởng đo từ dữ liệu:

- Incident enabled: `2026-08-11T08:25:23.835315Z`.
- Response ảnh hưởng đầu tiên: `2026-08-11T08:25:26.963035Z`.
- Response ảnh hưởng cuối: `2026-08-11T08:25:37.582185Z`.
- Incident disabled: `2026-08-11T08:25:38.042094Z`.

Dashboard vận hành chung dùng threshold P95 3.000 ms theo
`config/dashboard.yaml`, còn challenge dùng ngưỡng điều tra 2.000 ms. Vì vậy ảnh
dashboard có thể hiện `Within threshold` theo contract chung trong khi phép phân
tích CP3 vẫn xác nhận breach theo ngưỡng challenge; hai kết luận dùng hai contract
khác nhau và không mâu thuẫn.

Một giới hạn đo lường cần bàn giao: `response_sent.latency_ms` hiện đo thời gian
bên trong agent, trong khi load test concurrent quan sát wall-clock latency cao
hơn do thời gian chờ trước khi agent được thực thi. Dashboard vẫn dùng
`response_sent.latency_ms` đúng contract của bài; nếu dùng cho SLI production,
vai trò Middleware nên bổ sung request duration end-to-end để phản ánh đầy đủ trải
nghiệm người dùng. Nhận xét này không thay thế bằng chứng trace/log về root cause.

## Evidence bàn giao

- `submission/evidence/cp3-metrics-analysis.txt`: số liệu baseline/incident và
  khoảng thời gian ảnh hưởng.
- `submission/evidence/dashboard-cp3-incident.png`: dashboard sau challenge, P95
  hiển thị 2.651 ms trong cửa sổ 60 phút.

Ở lượt chạy CP3 ban đầu, nhánh chưa có feature metadata từ phần Logging, nên
script ghi rõ scope bằng phase marker. Sau khi merge phần Logging, evidence có thể
được scope trực tiếp theo `feature=monitoring`.

Việc chạy lại trên bản tích hợp đã hoàn thành ở CP4; xem
[CP4_DASHBOARD_FINAL_REVIEW.md](CP4_DASHBOARD_FINAL_REVIEW.md) và evidence
`submission/evidence/cp4-final-metrics-analysis.txt`.
