# Dựng và kiểm tra dashboard

`config/dashboard.yaml` là contract chấm điểm dùng chung, không phụ thuộc việc nhóm dựng dashboard trong Langfuse hay một công cụ local. File này quy định đúng nguồn dữ liệu, phép tổng hợp, đơn vị và threshold cho sáu panel.

Kết quả audit event/field ở CP1 được ghi tại
[CP1_DASHBOARD_LOG_AUDIT.md](CP1_DASHBOARD_LOG_AUDIT.md).
Phần triển khai và evidence runtime ở CP2 được ghi tại
[CP2_METRICS_DASHBOARD.md](CP2_METRICS_DASHBOARD.md).
Kết quả đọc metrics của challenge ở CP3 được ghi tại
[CP3_METRICS_FINDINGS.md](CP3_METRICS_FINDINGS.md).
Kết quả rà soát ảnh và bản tích hợp cuối được ghi tại
[CP4_DASHBOARD_FINAL_REVIEW.md](CP4_DASHBOARD_FINAL_REVIEW.md).

Trường `query` trong YAML là pseudocode mô tả phép tính, không phải câu lệnh để copy nguyên vào mọi công cụ. Nhóm chuyển cùng logic đó sang cú pháp của công cụ đã chọn.

## Mapping dữ liệu

| Panel | Event/field | Phép tổng hợp |
|---|---|---|
| Latency | `response_sent.latency_ms` | P50, P95, P99 |
| Traffic | `request_received` | count, request/phút |
| Errors | `request_received`, `request_failed`, `error_type` | error rate và breakdown |
| Cost | `response_sent.cost_usd` | tổng theo phút và toàn cửa sổ |
| Tokens | `response_sent.tokens_in/tokens_out` | tổng theo từng field |
| Quality | `response_sent.quality_score` | mean |

Giữ time range mặc định 60 phút, refresh 30 giây và hiển thị threshold/SLO line. Giá trị chính xác nằm trong `config/dashboard.yaml`; không tự đổi contract chỉ để ảnh dashboard đẹp hơn.

## Cách dựng

1. Hoàn thiện logging/PII và chạy API.
2. Chạy `python scripts/load_test.py --concurrency 5` để tạo baseline.
3. Mở `http://127.0.0.1:8000/dashboard`. Dashboard runtime đọc
   `data/logs.jsonl` và dựng đúng sáu panel; Langfuse vẫn là nơi mở
   trace/prompt version để điều tra sâu.
4. Đặt tên panel, đơn vị và threshold giống contract.
5. Chạy validator:

```bash
python scripts/validate_dashboard.py
```

Validator kiểm tra cấu trúc contract; nó không thể chứng minh biểu đồ trong ảnh dùng đúng dữ liệu. Evidence runtime vẫn bắt buộc.

Dashboard mặc định dùng cửa sổ 60 phút và tự tải lại sau 30 giây theo contract.
Nếu panel hiện `No data`, hãy chạy load test rồi refresh trang.

## Cách kiểm tra runtime

1. Lưu ảnh baseline và giá trị P95/error/cost hiện tại.
2. Bật một incident practice, ví dụ `python scripts/inject_incident.py --scenario rag_slow`.
3. Chạy lại load test với cùng input và concurrency.
4. Xác nhận panel liên quan thay đổi theo đúng hướng; với `rag_slow`, P95 phải tăng rõ ràng.
5. Mở trace chậm và tìm log có cùng correlation ID.
6. Tắt incident bằng `python scripts/inject_incident.py --scenario rag_slow --disable`.

Ảnh dashboard phải nhìn được tên panel, time range, đơn vị và threshold. Báo cáo phải dẫn lại trace ID hoặc log line dùng để giải thích thay đổi.
