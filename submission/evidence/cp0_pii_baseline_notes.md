# CP0 — PII baseline (Quang)

## Sample queries có PII (data/sample_queries.jsonl)
- u01: email dạng `student@***` (domain trường)
- u05: số điện thoại VN test, dạng `09xx-***-***`
- u09: số thẻ test, dạng `4111 **** **** ****` (mẫu thẻ test chuẩn Visa)
- Thiếu ca CCCD (12 số) — cần bổ sung test thủ công ở CP1.

Ghi chú: không chép nguyên văn giá trị test vào evidence, kể cả khi đó là
PII giả — theo checkpoint 1 (RULES.md), PII thử nghiệm cũng không được xuất
hiện nguyên văn. Giá trị gốc xem trực tiếp trong `data/sample_queries.jsonl`
khi cần đối chiếu.

## Kết quả baseline
Gửi 3 query trên tới `/chat` (server local, chưa bật Langfuse).
`data/logs.jsonl` tại thời điểm này đã lưu kèm trong file `cp0_pii_baseline_logs.jsonl`.

`message_preview` / `answer_preview` đã được redact đúng
(`[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]`).

## Phát hiện quan trọng
Việc redact ở trên đến từ `summarize_text()` (app/pii.py) được gọi trực tiếp
trong app/main.py — KHÔNG phải nhờ structlog processor `scrub_event`.
Processor này vẫn đang bị comment tại app/logging_config.py:45.
=> Chưa có lớp phòng thủ thứ 2 ở tầng logging cho các field string khác.
=> Việc của CP1: đăng ký `scrub_event`, bổ sung pattern (CCCD test, passport,
   địa chỉ), và test lại toàn bộ field trong log (kể cả request_failed.detail).
