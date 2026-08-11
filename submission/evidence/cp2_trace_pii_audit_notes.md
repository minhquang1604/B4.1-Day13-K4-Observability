# CP2 — Audit PII trên trace + log (Quang)

## Phạm vi
CP2 của role PII là đảm bảo KHÔNG chỉ file log (`data/logs.jsonl`) mà cả
**trace gửi lên Langfuse** không lộ PII. Đây là bề mặt rò rỉ khác với CP0/CP1
vì trace đi qua SDK Langfuse (`app/tracing.py`, `app/agent.py`), không đi qua
structlog/`scrub_event`.

## Audit code (app/agent.py)
1. `@observe(as_type="generation", capture_input=False, capture_output=False)`
   (agent.py:29) — ĐÃ tắt auto-capture của Langfuse SDK. Nếu thiếu 2 flag này,
   SDK sẽ tự log nguyên văn `message` (arg) và `answer` (return value) vào
   trace — lỗ hổng PII nghiêm trọng. Đã thêm test tĩnh canh gác việc này
   (`test_observe_decorator_disables_raw_input_output_capture`).
2. `update_current_trace(user_id=hash_user_id(user_id), ...)` — user_id gửi
   lên trace là bản hash SHA-256 (12 ký tự đầu), không phải user_id gốc.
3. `update_current_generation(metadata={"query_preview": summarize_text(message), ...})`
   — message chỉ xuất hiện trên trace dưới dạng đã qua `summarize_text()`
   (scrub PII + cắt 80 ký tự), không phải nguyên văn.
4. `session_id` gửi thẳng lên trace không hash — đây KHÔNG phải PII (chỉ là
   id phiên nội bộ do client tự sinh, không định danh cá nhân thật), nên
   chấp nhận được.

## Test mới: tests/test_trace_pii_redaction.py
- `test_trace_and_generation_metadata_do_not_leak_raw_pii`: gọi
  `LabAgent.run.__wrapped__` (bỏ qua network thật của Langfuse SDK, theo
  đúng pattern có sẵn ở test_agent_prompt_trace.py) với message chứa email +
  phone thật + raw user_id, assert:
  - `trace_update["user_id"]` == bản hash, không phải raw user_id.
  - Toàn bộ payload gửi lên trace (trace_update + generation_update)
    KHÔNG chứa raw email/phone/user_id.
  - `query_preview` chứa `[REDACTED_EMAIL]` / `[REDACTED_PHONE_VN]`.
- `test_observe_decorator_disables_raw_input_output_capture`: guard tĩnh đảm
  bảo `capture_input=False`/`capture_output=False` không bị xoá nhầm trong
  tương lai.

Kết quả: 2/2 passed (xem cp2_trace_pii_test_output.txt). Full suite: 27/27 passed.

## Giới hạn / việc còn lại
- Chưa có key Langfuse thật trong `.env` (phần setup thuộc CP2 của
  Tracing & Prompt Version — Hùng/nhóm). Audit ở đây dừng ở mức CODE + TEST
  (unit test, không gọi mạng thật).
- Khi nhóm có ≥10 trace thật trên Langfuse UI, cần làm thêm 1 bước thủ công:
  mở vài trace ngẫu nhiên trên UI, kiểm tra bằng mắt các trường
  input/output/metadata không hiện raw PII, rồi chụp lại làm evidence bổ
  sung (không thể tự động hoá bước này vì cần tài khoản Langfuse thật).
