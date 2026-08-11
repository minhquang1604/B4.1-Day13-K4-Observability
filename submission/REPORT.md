# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: **B4.1**.
- Repository URL: [K4-DAY13-2A202601884](https://github.com/minhquang1604/K4-DAY13-2A202601884.git).
- Commit SHA cuối: 02cf21a612985d4a3052025cffe0669131ba9814.
- Thành viên và vai trò:
  - Điền Mạnh Hùng — `2A202601888`: SRE, SLO, alert và runbook.
  - Nguyễn Lâm Tùng Bách — `2A202601830`: metrics và dashboard.
  - Trần Phú Nghĩa — `2A20260233871`: middleware, correlation ID và log–trace correlation.
  - Cao Minh Quang — `2A202601884`: PII redaction và kiểm tra secret/PII.
  - Trần Minh Quang — `2A202601856`: QA, trace spans và điều tra challenge.


## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** trên log sạch sau CP1 ([evidence correlation ID](evidence/cp1-correlation-id-after.txt)); không dùng baseline CP0 30/100 để đánh giá kết quả cuối.
- Tổng số traces có evidence: **11** trace log-correlation ban đầu và **10 trace managed prompt QA**; xem [evidence CP2 correlation](evidence/cp2-log-trace-correlation.txt) và [managed prompt versioning](evidence/cp2-managed-prompt-versioning.md).
- Số PII leak còn lại: **0**; xem [final PII/secret audit](evidence/final_pii_secret_audit.md).
- Link/đường dẫn dashboard: route `/dashboard` khi chạy app; evidence cuối: [dashboard-final.png](evidence/dashboard-final.png).

### Baseline CP0 (2026-08-11)

- API chạy cục bộ tại `http://127.0.0.1:8001` vì cổng 8000 đang được một dịch vụ khác sử dụng.
- Đã chạy 10 request mẫu; `data/logs.jsonl` có 23 records.
- `python scripts/validate_logs.py`: **30/100** — thiếu correlation ID và request-context enrichment; PII leak: 0.
- `python scripts/validate_dashboard.py`: **HỢP LỆ: 6/6 panel**.
- `python -m pytest -q`: **22 passed**.

## 3. Logging và tracing

- Evidence correlation ID: [cp1-correlation-id-after.txt](evidence/cp1-correlation-id-after.txt) (header round-trip, 0 rò context ở `--concurrency 5`, validator 30/100 → 100/100) và [cp2-log-trace-correlation.txt](evidence/cp2-log-trace-correlation.txt) (11/11 record ghép 1-1 `correlation_id` ↔ `trace_id`).
- Evidence PII redaction: [cp1_pii_redaction_notes.md](evidence/cp1_pii_redaction_notes.md), [cp1_pii_redaction_logs.jsonl](evidence/cp1_pii_redaction_logs.jsonl).
- Evidence trace waterfall: [trace baseline v1 `21078f5a...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/21078f5a7f64abd98de7dab1fa5b2cb3) và [trace candidate v2 `9c23cd22...`](https://cloud.langfuse.com/project/cmsocqvkb01qjad0gjiivg97d/traces/9c23cd2239f2e7eec6140954d85a9f3e) đều có observation `rag_retrieve`/`llm_generate`; metadata và 10 trace QA được ghi tại [managed prompt evidence](evidence/cp2-managed-prompt-versioning.md).
- Giải thích một span đáng chú ý: `rag_retrieve` là span bất thường khi `rag_slow` bật vì retrieval block 2.5 giây; `llm_generate` chỉ khoảng 150 ms. Chênh lệch này, cùng P95 tăng hơn 2.5 giây, khoanh vùng retrieval là nguyên nhân trực tiếp.

### Middleware và correlation ID (Nghĩa)

Ba cơ chế trong [app/middleware.py](../app/middleware.py) và [app/main.py](../app/main.py):

1. `clear_contextvars()` chạy đầu mỗi request. Contextvars sống sót giữa các request trên cùng worker task, không xóa thì context request trước rò sang request sau — chỉ lộ ra khi chạy đồng thời.
2. Header `x-request-id` chỉ được tái sử dụng khi khớp `^req-[0-9a-f]{8}$`, sai thì sinh mới. Header do client kiểm soát; nhận nguyên xi thì giá trị đó đi vào mọi dòng log của request, thành log injection và nổ cardinality khi query. Đánh đổi có ý thức: correlation ID từ service upstream khác định dạng sẽ bị bỏ.
3. Liên kết hai chiều log ↔ trace: log `response_sent` mang `trace_id` (mở thẳng Langfuse từ log), generation metadata mang `correlation_id` (grep ngược ra log từ trace). `correlation_id` đặt ở **generation** chứ không phải trace metadata vì test công khai [tests/test_agent_prompt_trace.py](../tests/test_agent_prompt_trace.py) khóa cứng trace metadata bằng đúng 4 key prompt — không sửa test của Lab Coach để code mình pass.

`current_trace_id()` nuốt exception và trả `None`: Langfuse hỏng không được phép làm chết request mà nó đang quan sát. Có test riêng cho trường hợp này.

**Giới hạn đã biết — liên quan trực tiếp tới preventive measure #1 ở mục 6.** Header `x-response-time-ms` và field `latency_ms` **không thể** đo được queue wait, và metric `queue_wait_ms` cũng không cài đặt được trong middleware này. Lý do: khi event loop bị chặn, `dispatch()` của middleware chưa hề bắt đầu chạy, nên mốc `start` được ghi *sau* khi đã xếp hàng xong. Đó chính là vì sao `latency_ms` server-side báo 3.6s trong khi client chờ 17.9s. Muốn đo queue wait phải lấy mốc ở tầng ASGI server hoặc đối chiếu timestamp do client gửi kèm, không phải ở middleware ứng dụng.

Rà soát tại commit tích hợp `78805cf`: `pytest` 43 passed; `validate_dashboard.py` 6/6 panel, 7/7 field; smoke test một request có PII trả header `x-request-id: req-11223344` + `x-response-time-ms: 1202.93`, log ghi đủ `correlation_id`/`trace_id`/enrichment và che `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `grep` không thấy email/số điện thoại nguyên văn. Final QA sau đó vẫn giữ nguyên 43 tests pass và các validator đều đạt.

### SRE acceptance gate — CP1 (Hùng)

**Đã sign-off:** `validate_logs.py` đạt 100/100, vượt gate tối thiểu 80/100; final QA có 20 records, 10 correlation IDs và 0 PII leak. Với mỗi event của `service=api`, log cho phép SRE trả lời được **request nào, đang ở môi trường nào, ảnh hưởng gì và có thể liên kết evidence nào**:

- `correlation_id` hợp lệ, xuất hiện xuyên suốt request/response và trả về qua header để nối metrics → traces → logs.
- Context request bắt buộc: `env`, `user_id_hash`, `session_id`, `feature`, `model`; chỉ dùng hash cho user ID và không ghi PII nguyên văn.
- `response_sent` phải có `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score` để đo SLO latency/cost/quality.
- `request_failed` phải có `error_type` và cùng context để alert có thể phân loại ảnh hưởng theo lỗi thay vì theo implementation nội bộ.
- Điều kiện đưa vào CP2 đã đạt: có ít nhất 2 correlation ID riêng biệt, không còn PII leak, và log đủ trường để dashboard dùng `data/logs.jsonl` làm nguồn chuẩn.

Mục tiêu SLO đã được giữ theo contract: P95 latency ≤ 3000 ms, error rate ≤ 2%, daily cost ≤ 2.5 USD và quality trung bình ≥ 0.75. Alert rule/runbook cụ thể sẽ được triển khai ở CP2 sau khi các tín hiệu này được xác thực.

## 4. Prompt versioning

- Prompt name: `day13-chat`.
- Version/label baseline: **v1**, labels cuối `baseline`, `production`.
- Version/label candidate: **v2**, labels cuối `candidate`, `latest`.
- Trace ID mỗi version: baseline v1 `21078f5a7f64abd98de7dab1fa5b2cb3`; candidate v2 `9c23cd2239f2e7eec6140954d85a9f3e`.
- Bằng chứng đổi label/rollback: đã chuyển `production` sang v2 và xác minh bằng trace `c308216c1542c32260ef4c5041914285`; sau đó rollback về v1 và xác minh bằng trace `c6107a2d17d81fc90a9d61c19e6c68d4`. Trạng thái cuối đã đọc lại qua API: v1 giữ `production`. Chi tiết và direct links: [CP2 managed prompt versioning](evidence/cp2-managed-prompt-versioning.md).

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **HỢP LỆ: 6/6 panel; 7/7 field có trong logging schema**.
- Evidence dashboard: [dashboard-final.png](evidence/dashboard-final.png), [CP4 dashboard review](../docs/CP4_DASHBOARD_FINAL_REVIEW.md) và [CP4 metrics analysis](evidence/cp4-final-metrics-analysis.txt).
- SLO đã chọn và lý do: P95 latency ≤ 3000 ms, error rate ≤ 2%, daily cost ≤ 2.5 USD và quality trung bình ≥ 0.75, khớp với dashboard contract để một tín hiệu có thể được phát hiện và điều tra bằng cùng dữ liệu log.
- Alert rules và runbook: [config/alert_rules.yaml](../config/alert_rules.yaml) và [docs/alerts.md](../docs/alerts.md) — alert tail latency, error rate và daily cost; mỗi alert có severity, owner Hùng (SRE), condition, triage Metrics → Traces → Logs và mitigation tạm thời.

### CP4 SRE handoff (Hùng)

- Kiểm tra cuối: `python scripts/validate_dashboard.py` hợp lệ 6/6 panel và 7/7 logging fields; `python -m pytest -q` có 43 tests passed.
- Demo SRE: mở panel Latency để chỉ ra P95 vượt ngưỡng, mở trace của request chậm để so sánh `rag_retrieve` với `llm_generate`, sau đó dùng `correlation_id` tìm log tương ứng và đọc mitigation trong Alert 1.
- QA cuối: `validate_logs.py` đạt 100/100 trên 20 records/10 correlation IDs; 10 managed traces đã được API xác minh đủ prompt metadata. Kết quả tổng hợp ở [final-validation.txt](evidence/final-validation.txt).
- Evidence UI cần lưu thủ công trước khi nộp: ảnh danh sách prompt v1/v2, trạng thái switch `production` sang v2, rollback về v1 và trace waterfall; tên file/đường dẫn mở trực tiếp được ghi trong [managed prompt evidence](evidence/cp2-managed-prompt-versioning.md).

## 6. Điều tra challenge

- Challenge ID: `day13-k4-observability-v1` (cohort K4, incident `rag_slow`, `affected_feature=monitoring`, `latency_threshold_ms=2000`, xem `config/challenge.json`).
- Triệu chứng từ metrics: baseline (10 request) có P50/P95/P99 = 151 ms. Khi chạy workload challenge với `rag_slow`, P95/P99 = 2659 ms, vượt challenge threshold 2000 ms. Một lần chạy Langfuse-enabled riêng cũng ghi P95/P99 = 3481 ms; chênh lệch do môi trường/prompt resolution khác nhau, nhưng cả hai lần đều xác nhận tail latency là triệu chứng chính. Chi tiết: `submission/evidence/cp3_load_test_and_metrics.md` và [CP3 rag_slow investigation](evidence/cp3-rag-slow-investigation.md).
- Trace ID challenge liên quan: `7bc2c339e500086c3e0f504cf3d15458`, latency 3.483 s. Code cuối đã có span `rag_retrieve` ([mock_rag.py](../app/mock_rag.py)) và generation `llm_generate` ([mock_llm.py](../app/mock_llm.py)); các trace managed mới xác nhận instrumentation này hoạt động, còn trace challenge dùng để chứng minh hiện tượng `rag_slow`.
- Log line/correlation ID liên quan: evidence challenge ban đầu trong `submission/evidence/cp3_challenge_logs.jsonl` được tạo trước khi middleware được tích hợp nên phải đối chiếu bằng timestamp/nội dung message:
  - `incident_enabled` lúc `07:55:31.841959Z` (bật `rag_slow`).
  - 5 dòng `request_received` của 5 query challenge cách nhau đều đặn **~2.65s** dù được gửi đồng thời với `--concurrency 5`: `07:55:39.543`, `07:55:42.202`, `07:55:44.858`, `07:55:47.522`, `07:55:50.176`.
  - 5 dòng `response_sent` tương ứng đều có `latency_ms≈2650-2659`, khớp với thời gian `time.sleep(2.5)` được inject trong `retrieve()` (`app/mock_rag.py`) cộng ~150ms gọi LLM (`app/mock_llm.py`).
- Root cause: hai lớp nguyên nhân, cả hai đều được chứng minh bằng log/metric ở trên.
  1. **Nguyên nhân theo kịch bản incident**: `rag_slow=True` khiến `retrieve()` block 2.5s mỗi lần gọi (`app/mock_rag.py:18`) — chiếm ~94% latency của mỗi request (2.5s/2.65s), trong khi phần LLM chỉ ~150ms. Đây chính là span sẽ hiện "bất thường" khi xem trace waterfall sau khi bật Langfuse.
  2. **Yếu tố khuếch đại phát hiện qua load test**: endpoint `POST /chat` khai báo `async def` nhưng gọi thẳng `agent.run(...)` là hàm đồng bộ, blocking (`app/main.py:68`), không dùng `run_in_threadpool`/`asyncio.to_thread`. Vì vậy lệnh `time.sleep(2.5)` bên trong chặn luôn event loop của Uvicorn, khiến 5 request gửi đồng thời bị xử lý tuần tự thay vì song song — 5 dòng `request_received` cách đều 2.65s là bằng chứng trực tiếp. Kết quả là độ trễ client thấy được (10.7s–13.3s, đo bởi `scripts/load_test.py`) cao hơn nhiều so với `latency_ms` nội bộ (~2.65s) ghi trong log — một khoảng "queue wait" hiện không được đo bằng metric nào cả. Nghĩa độc lập ghi nhận đúng hiện tượng này ở mục 3 (dòng "Giới hạn đã biết") kèm giải thích vì sao `queue_wait_ms` không thể đo được trong middleware: `dispatch()` chỉ bắt đầu chạy sau khi request đã xếp hàng xong, nên mốc `start` bị ghi trễ.
- Fix action:
  1. Khắc phục root cause 1 (theo kịch bản lab, không sửa `mock_rag.py` vì đó là script mô phỏng incident dùng chung — hành động fix thực tế là: thêm timeout + retry/circuit breaker quanh lời gọi vector store thật, và cảnh báo khi span `rag_retrieve` vượt ngưỡng).
  2. Khắc phục root cause 2 (áp dụng được ngay, không đụng tới phần việc của thành viên khác vì đây đúng là phần "chạy load test và điều tra" của vai trò E): chuyển lời gọi `agent.run(...)` trong `app/main.py` sang chạy trong threadpool (`await run_in_threadpool(agent.run, ...)` hoặc `await asyncio.to_thread(...)`) để một request chậm không chặn toàn bộ event loop và làm khuếch đại tail latency của các request khác.
- Preventive measure:
  1. Thêm metric `queue_wait_ms` bên cạnh `latency_ms` hiện tại, để phân biệt "chậm do RAG" và "chậm do bị xếp hàng" — hiện `/metrics` chỉ thấy phần sau. Lưu ý (theo mục 3, Nghĩa): không đo được ở `CorrelationIdMiddleware`, vì middleware application-level chỉ bắt đầu chạy sau khi request đã qua hàng đợi của event loop; phải lấy mốc thời gian ở tầng ASGI server (Uvicorn) hoặc client gửi kèm timestamp để trừ lại.
  2. Thêm alert riêng cho span `rag_retrieve` (sau khi bật Langfuse) khi p95 vượt một ngưỡng, tách khỏi alert latency tổng, để không phải đoán span nào gây chậm mỗi lần incident xảy ra.
  3. Chạy load test định kỳ (đã có `scripts/load_test.py --concurrency`) như một phần CI/pre-release check để bắt sớm các trường hợp blocking-call-trong-async-handler tương tự trước khi lên production.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Điền Mạnh Hùng | SLO, ba alert symptom-based, runbook, SRE acceptance gate và evidence incident `rag_slow` | `100c39a`, `ef46424`, `779f16f`, `169d63f` | Điều tra phải nối metrics → trace → log bằng correlation ID; latency tổng cần tách với queue wait để chọn đúng mitigation. |
| Nguyễn Lâm Tùng Bách | Contract log cho dashboard, sáu panel runtime, SLO threshold và evidence dashboard/metrics CP3–CP4 | `66b42b8`, `bdf7776`, `577a212`, `d40c8f3` | P95, traffic, error, cost, token và quality cần cùng dùng structured logs và có ngưỡng rõ ràng để phát hiện incident. |
| Trần Phú Nghĩa | Middleware correlation ID, request-context enrichment, log ↔ trace correlation, test và investigation tầng log | `56cf9bd`, `0d9e3ee`, `30c40f9`, `d7ce9f4` | Correlation ID và timestamp log có thể chứng minh queue wait mà metric server-side không đo được. |
| Cao Minh Quang | PII scrubber, audit PII trong log/trace và rà soát secret/PII trước push | `00ba3a0`, `756ad7a`, `73cb068`, `b829ef8` | Redaction phải diễn ra trước JSON rendering và phải audit cả log lẫn metadata trace. |
| Trần Minh Quang | QA, load test practice/challenge, instrumentation `rag_retrieve`/`llm_generate`, managed prompt v1/v2, kiểm chứng label switch/rollback và điều tra CP3 | `245ec00`, `4b175b9`; commit final QA do Hùng tạo sau khi review | Blocking call trong `async def` chặn event loop; prompt label cho phép rollout/rollback mà không đổi code và trace metadata phải ghi rõ version thực thi. |
