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
- SLO đã chọn và lý do: P95 latency ≤ 3000 ms, error rate ≤ 2%, daily cost ≤ 2.5 USD và quality trung bình ≥ 0.75, khớp với dashboard contract để một tín hiệu có thể được phát hiện và điều tra bằng cùng dữ liệu log.
- Alert rules và runbook: [config/alert_rules.yaml](../config/alert_rules.yaml) và [docs/alerts.md](../docs/alerts.md) — alert tail latency, error rate và daily cost; mỗi alert có severity, owner Hùng (SRE), condition, triage Metrics → Traces → Logs và mitigation tạm thời.

## 6. Điều tra challenge

- Challenge ID: `day13-k4-observability-v1` (cohort K4, incident `rag_slow`, `affected_feature=monitoring`, `latency_threshold_ms=2000`, xem `config/challenge.json`).
- Triệu chứng từ metrics: baseline (`python scripts/load_test.py`, 10 requests) cho `latency_p50=p95=p99=151ms`. Sau khi chạy `python scripts/inject_incident.py` rồi `python scripts/load_test.py --challenge --concurrency 5`, `GET /metrics` báo `latency_p95=latency_p99=2659ms` — vượt xa ngưỡng `latency_threshold_ms=2000` của challenge. Chi tiết: `submission/evidence/cp3_load_test_and_metrics.md`.
- Trace ID liên quan: chưa có, vì môi trường chạy investigation này không có `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` (`GET /health` báo `tracing_enabled:false`). Đã bọc thêm span con `rag_retrieve` (trong [`app/mock_rag.py`](../app/mock_rag.py)) và generation con `llm_generate` (trong [`app/mock_llm.py`](../app/mock_llm.py)) — phần mở rộng của Thành viên E — để khi bật Langfuse, trace waterfall tách rõ thời gian retrieval so với thời gian gọi LLM thay vì gộp chung một span `LabAgent.run`. Thành viên phụ trách Tracing cần bật Langfuse keys và chụp lại trace waterfall thật làm evidence chính thức.
- Log line/correlation ID liên quan: correlation ID hiện chưa gán (middleware TODO ở [`app/middleware.py`](../app/middleware.py) chưa hoàn thiện, ngoài phạm vi vai trò E) nên đối chiếu bằng timestamp/nội dung message. Bằng chứng trong `submission/evidence/cp3_challenge_logs.jsonl`:
  - `incident_enabled` lúc `07:55:31.841959Z` (bật `rag_slow`).
  - 5 dòng `request_received` của 5 query challenge cách nhau đều đặn **~2.65s** dù được gửi đồng thời với `--concurrency 5`: `07:55:39.543`, `07:55:42.202`, `07:55:44.858`, `07:55:47.522`, `07:55:50.176`.
  - 5 dòng `response_sent` tương ứng đều có `latency_ms≈2650-2659`, khớp với thời gian `time.sleep(2.5)` được inject trong `retrieve()` (`app/mock_rag.py`) cộng ~150ms gọi LLM (`app/mock_llm.py`).
- Root cause: hai lớp nguyên nhân, cả hai đều chứng minh được bằng log/metric ở trên.
  1. **Nguyên nhân theo kịch bản incident**: `rag_slow=True` khiến `retrieve()` block 2.5s mỗi lần gọi (`app/mock_rag.py:18`) — chiếm ~94% latency của mỗi request (2.5s/2.65s), trong khi phần LLM chỉ ~150ms. Đây chính là span sẽ hiện "bất thường" khi xem trace waterfall sau khi bật Langfuse.
  2. **Yếu tố khuếch đại phát hiện qua load test**: endpoint `POST /chat` khai báo `async def` nhưng gọi thẳng `agent.run(...)` là hàm đồng bộ, blocking (`app/main.py:56`), không dùng `run_in_threadpool`/`asyncio.to_thread`. Vì vậy lệnh `time.sleep(2.5)` bên trong chặn luôn event loop của Uvicorn, khiến 5 request gửi đồng thời bị xử lý tuần tự thay vì song song — 5 dòng `request_received` cách đều 2.65s là bằng chứng trực tiếp. Kết quả là độ trễ client thấy được (7.9s–13.3s, đo bởi `scripts/load_test.py`) cao hơn nhiều so với `latency_ms` nội bộ (~2.65s) ghi trong log — một khoảng "queue wait" hiện không được đo bằng metric nào cả.
- Fix action:
  1. Khắc phục root cause 1 (theo kịch bản lab, không sửa `mock_rag.py` vì đó là script mô phỏng incident dùng chung — hành động fix thực tế là: thêm timeout + retry/circuit breaker quanh lời gọi vector store thật, và cảnh báo khi span `rag_retrieve` vượt ngưỡng).
  2. Khắc phục root cause 2 (áp dụng được ngay, không đụng tới phần việc của thành viên khác vì đây đúng là phần "chạy load test và điều tra" của vai trò E): chuyển lời gọi `agent.run(...)` trong `app/main.py` sang chạy trong threadpool (`await run_in_threadpool(agent.run, ...)` hoặc `await asyncio.to_thread(...)`) để một request chậm không chặn toàn bộ event loop và làm khuếch đại tail latency của các request khác.
- Preventive measure:
  1. Thêm metric `queue_wait_ms` (thời gian từ lúc request tới lúc bắt đầu xử lý) bên cạnh `latency_ms` hiện tại, để phân biệt "chậm do RAG" và "chậm do bị xếp hàng" — hiện `/metrics` chỉ thấy phần sau.
  2. Thêm alert riêng cho span `rag_retrieve` (sau khi bật Langfuse) khi p95 vượt một ngưỡng, tách khỏi alert latency tổng, để không phải đoán span nào gây chậm mỗi lần incident xảy ra.
  3. Chạy load test định kỳ (đã có `scripts/load_test.py --concurrency`) như một phần CI/pre-release check để bắt sớm các trường hợp blocking-call-trong-async-handler tương tự trước khi lên production.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| E (QA & Chief Investigator) | Chạy load test practice và challenge (`scripts/load_test.py`); bọc trace `rag_retrieve`/`llm_generate` cho sub-component RAG/LLM (`app/mock_rag.py`, `app/mock_llm.py`); điều tra CP3 (`config/challenge.json`) và viết mục 6 báo cáo | *(điền commit SHA sau khi commit)* | Blocking call trong `async def` FastAPI handler chặn cả event loop và khuếch đại tail latency dưới tải đồng thời — phải phân biệt `latency_ms` nội bộ với latency client thấy được (queue wait) khi điều tra incident. |
| | | | |
