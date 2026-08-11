# CP3 — Audit PII trên incident evidence (Quang)

## Bối cảnh
Chạy challenge chính thức (config/challenge.json, id
day13-k4-observability-v1, incident rag_slow):

```bash
python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5
```

5/5 request trả 200, latency tăng rõ rệt (2.6s–13.3s, đúng dấu hiệu rag_slow
so với threshold 2000ms trong challenge.json) — xem
cp3_challenge_pii_audit_logs.jsonl.

## Audit PII
- 5 câu hỏi challenge không chứa PII theo thiết kế (đã đọc trước nội dung
  config/challenge.json để xác nhận).
- `user_id_hash` cho k4-u01..k4-u05 là bản hash SHA-256 rút gọn (vd
  `f00ba60b3772`), KHÔNG phải raw user_id — cơ chế `hash_user_id()` hoạt
  động đúng kể cả với user_id do challenge sinh ra (không chỉ user_id demo).
- `session_id` (k4-challenge-s0x) là id nội bộ do challenge tự sinh, không
  phải thông tin định danh cá nhân thật — chấp nhận được, không cần redact.
- `correlation_id` (req-*) và `trace_id` mới xuất hiện trong log (nhờ
  middleware correlation của Nghĩa + trace correlation của Nghĩa CP2) — đều
  là chuỗi hex ngẫu nhiên sinh tại runtime, không phải PII.
- grep toàn bộ log tìm mẫu email/số điện thoại/số thẻ dạng số liên tục:
  0 kết quả nghi vấn (ngoài các entry test PII CP0/CP1 đã redact đúng từ
  trước, còn sót lại trong cùng file).

## Kết luận
Evidence cho challenge (log, correlation_id, trace_id) sẵn sàng để đưa vào
submission/REPORT.md mục 6 (Điều tra challenge) mà KHÔNG cần redact thêm —
đã sạch PII. Người phụ trách điều tra root cause (QA/CP3) có thể dùng trực
tiếp file log/trace này làm bằng chứng, không cần qua Quang xử lý lại.

`scripts/validate_logs.py` sau challenge run: xem cp3_validate_logs_output.txt.
