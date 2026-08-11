# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`:
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard:

### Baseline CP0 (2026-08-11)

- API chạy cục bộ tại `http://127.0.0.1:8001` vì cổng 8000 đang được một dịch vụ khác sử dụng.
- Đã chạy 10 request mẫu; `data/logs.jsonl` có 23 records.
- `python scripts/validate_logs.py`: **30/100** — thiếu correlation ID và request-context enrichment; PII leak: 0.
- `python scripts/validate_dashboard.py`: **HỢP LỆ: 6/6 panel**.
- `python -m pytest -q`: **22 passed**.

## 3. Logging và tracing

- Evidence correlation ID:
- Evidence PII redaction:
- Evidence trace waterfall:
- Giải thích một span đáng chú ý:

### SRE acceptance gate — CP1 (Hùng)

Chưa sign-off cho đến khi CP1 có bằng chứng chạy lại `validate_logs.py` đạt tối thiểu 80/100. Với mỗi event của `service=api`, log phải cho phép SRE trả lời được **request nào, đang ở môi trường nào, ảnh hưởng gì và có thể liên kết evidence nào**:

- `correlation_id` hợp lệ, xuất hiện xuyên suốt request/response và trả về qua header để nối metrics → traces → logs.
- Context request bắt buộc: `env`, `user_id_hash`, `session_id`, `feature`, `model`; chỉ dùng hash cho user ID và không ghi PII nguyên văn.
- `response_sent` phải có `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score` để đo SLO latency/cost/quality.
- `request_failed` phải có `error_type` và cùng context để alert có thể phân loại ảnh hưởng theo lỗi thay vì theo implementation nội bộ.
- Điều kiện đưa vào CP2: có ít nhất 2 correlation ID riêng biệt, không còn PII leak, và log đủ trường để dashboard dùng `data/logs.jsonl` làm nguồn chuẩn.

Mục tiêu SLO đã được giữ theo contract: P95 latency ≤ 3000 ms, error rate ≤ 2%, daily cost ≤ 2.5 USD và quality trung bình ≥ 0.75. Alert rule/runbook cụ thể sẽ được triển khai ở CP2 sau khi các tín hiệu này được xác thực.

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| | | | |
