# Final QA checklist — nhóm B4.1

Ngày kiểm tra: 2026-08-11.

| Checkpoint | Kết quả | Bằng chứng chính |
|---|---|---|
| CP0 — setup/baseline | PASS | API/load test hoạt động; baseline `validate_logs.py` 30/100 được lưu tại `cp0-baseline-validate-logs.txt`. |
| CP1 — logging/PII | PASS | Final validator 100/100; 10 correlation IDs; 0 thiếu schema/enrichment; 0 PII leak. |
| CP2 — metrics/traces/dashboard | PASS về kỹ thuật | Dashboard 6/6 panel, 7/7 field; 10 managed traces; prompt v1/v2; switch và rollback `production` đã xác minh. Ảnh UI Langfuse cần người dùng đăng nhập và lưu thủ công theo `cp2-managed-prompt-versioning.md`. |
| CP3 — challenge | PASS | Metrics vượt threshold, trace/span khoanh vùng `rag_retrieve`, log/timestamp chứng minh root cause và yếu tố blocking event loop; fix/preventive measures đã ghi trong REPORT. |
| Hoàn tất — report/security | PASS | REPORT đủ thông tin 5 thành viên; 43 tests pass; dashboard/log validators pass; `.env` ignored; gitlink `langfuse-local` lỗi đã bỏ khỏi index. |

## Kết quả lệnh cuối

- `pytest`: 43 passed.
- `validate_logs.py`: 100/100.
- `validate_dashboard.py`: 6/6 panel, 7/7 field.
- `git diff --check`: không có whitespace error.

## Việc thủ công trước commit

Do ảnh UI yêu cầu phiên đăng nhập Langfuse của người dùng, hãy lưu bốn ảnh được
liệt kê trong `cp2-managed-prompt-versioning.md`, sau đó chạy lại bộ lệnh final.
