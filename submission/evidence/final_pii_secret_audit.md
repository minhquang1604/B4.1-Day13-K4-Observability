# Hoàn tất — Rà soát PII/secret trước push (Quang)

## Việc đã kiểm tra
1. `.env` chưa từng được commit vào git history (`git log --all --full-history -- .env` rỗng).
2. `.env` và `.venv/` không nằm trong danh sách file được track (`git ls-files`).
3. Grep toàn bộ file đang track tìm secret pattern (Langfuse key thật,
   AWS key, private key block) — chỉ khớp placeholder rỗng/`...` trong
   `SETUP.md`, không phải secret thật.
4. Grep toàn bộ file đang track tìm email lạ, số điện thoại, số thẻ dạng thô
   — sạch.
5. Phát hiện và sửa lỗi: 2 file evidence (`cp0_pii_baseline_notes.md`,
   `cp2_trace_pii_test_output.txt`) từng chứa PII thử nghiệm nguyên văn
   (do lỗi thao tác — chạy `pytest` không kích hoạt `.venv` nên dùng nhầm
   Python hệ thống, khiến 1 test báo FAILED sai và output còn sót source
   code chứa PII giả). Đã regenerate với `.venv` active và viết lại notes
   không chép nguyên văn giá trị test.
6. Chạy lại toàn bộ để xác nhận trạng thái cuối cùng đúng:
   - `pytest -q`: 43/43 passed.
   - `scripts/validate_logs.py`: 100/100; 20 records, 10 correlation IDs,
     không thiếu schema/enrichment và 0 PII leak.
   - `scripts/validate_dashboard.py`: hợp lệ 6/6 panel và 7/7 logging field.

## Kết luận
Bản tích hợp cuối của nhóm B4.1 sẵn sàng để review trước push — không có secret,
không có PII nguyên văn (kể cả PII thử nghiệm) trong bất kỳ file nào đang được
track bởi Git.

## Bài học rút ra (để note vào REPORT.md phần cá nhân)
Môi trường Bash trong phiên làm việc này KHÔNG giữ lại trạng thái
`source .venv/bin/activate` giữa các lệnh riêng lẻ — mỗi lần chạy script
kiểm chứng (test, validator) phải activate venv lại trong cùng một lệnh,
nếu không sẽ vô tình chạy bằng Python hệ thống (thiếu dependency, hành vi
khác) và tạo ra evidence sai lệch. Đây là lý do CP2 evidence ban đầu bị sai.
