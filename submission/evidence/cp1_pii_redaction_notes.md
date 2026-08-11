# CP1 — PII scrubber bật + pattern mở rộng (Quang)

## Thay đổi
- app/logging_config.py: đăng ký processor `scrub_event` vào pipeline structlog
  (lớp phòng thủ thứ 2, độc lập với `summarize_text()` trong main.py).
- app/pii.py: thêm 2 pattern mới
  - `passport_vn`: hộ chiếu VN (1 chữ + 7 số, vd B1234567)
  - `address_vn`: từ khoá địa chỉ VN có dấu (số nhà, đường, phố, ngõ, hẻm,
    phường, xã, quận, huyện, thị xã, thành phố, tp., tỉnh) + tối đa 3 từ theo sau
  - Áp dụng `re.IGNORECASE` cho toàn bộ pattern.
- tests/test_pii.py: thêm test cho passport, address, và 1 test chống false
  positive trên câu tiếng Anh thường (không PII).

## Giới hạn đã biết
- `address_vn` chỉ bắt được khi từ khoá có dấu tiếng Việt đầy đủ
  (vd "đường", "quận"); dạng không dấu ("duong", "quan") KHÔNG được bắt.
  => Ghi vào report như một known limitation, không phải bug.
- Pattern địa chỉ dựa trên từ khoá, có thể redact hơi rộng (vd cụm sau từ
  khoá không thực sự là địa chỉ) — chấp nhận được cho mục tiêu "không lộ PII"
  hơn là độ chính xác tuyệt đối.

## Kết quả test
- `pytest tests/test_pii.py`: 5/5 passed.
- `pytest -q` (toàn repo): 25/25 passed.
- `scripts/validate_logs.py`: mục "PII scrubbing" = PASSED (xem
  cp1_validate_logs_output.txt). 3 mục FAILED còn lại (correlation ID,
  enrichment, required fields) thuộc phần việc của Nghĩa (middleware/main.py),
  không thuộc phạm vi PII.
- 6 ca test gửi qua `/chat` (email, phone, credit card, CCCD, hộ chiếu, địa chỉ)
  đều được redact đúng trong `data/logs.jsonl` — xem cp1_pii_redaction_logs.jsonl.
