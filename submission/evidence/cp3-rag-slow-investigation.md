# CP3 — Điều tra incident `rag_slow`

- Challenge: `day13-k4-observability-v1` (K4).
- Incident được bật: `rag_slow`.
- Workload: 5 request chính thức với concurrency 5; tất cả trả HTTP 200.

## Metrics

Snapshot trước incident: traffic 0, P95 latency 0 ms, error breakdown rỗng.

Snapshot sau workload:

| Signal | Giá trị | Đánh giá |
|---|---:|---|
| Traffic | 5 | Có đủ workload challenge |
| Latency P50 | 3471 ms | Cao |
| Latency P95/P99 | 3481 ms | Vượt SLO 3000 ms và challenge threshold 2000 ms |
| Error rate | 0% | Không phải triệu chứng chính |
| Total cost | 0.0102 USD | Bình thường |
| Quality average | 0.84 | Bình thường |

## Trace và log evidence

- Trace ID: `7bc2c339e500086c3e0f504cf3d15458`.
- Langfuse trace path: `/project/cmsocqvkb01qjad0gjiivg97d/traces/7bc2c339e500086c3e0f504cf3d15458`.
- Trace latency: 3.483 s; observation `GENERATION/run` (`ad43459ef63fa57b`) cũng dài 3.483 s.
- Log tương ứng trong `data/logs.jsonl`: event `response_sent`, timestamp `2026-08-11T08:10:20.083058Z`, `latency_ms=3481`; request bắt đầu tại `2026-08-11T08:10:16.599225Z`. Feature `monitoring` lấy từ payload challenge; log chưa lưu context này.

Limitation: log hiện chưa có correlation ID hợp lệ (giá trị là `MISSING`), và trace chỉ có generation span bao toàn bộ `LabAgent.run`. Do đó, trace cho thấy request bất thường nhưng chưa cô lập được retrieval bằng span riêng; đây là một gap phải sửa trước demo cuối.

## Root cause, fix và phòng ngừa

- Root cause được chứng minh ở `app/mock_rag.py`: khi `STATE["rag_slow"]` bật, `retrieve()` gọi synchronous `time.sleep(2.5)`. Hàm này chạy trong request path async, làm tăng latency và chặn xử lý concurrent requests.
- Fix: thay retrieval blocking bằng client async hoặc chạy dependency sync trong thread pool, có timeout; trả fallback an toàn khi retrieval quá budget.
- Prevention: tạo span `retrieval` riêng với timeout/result metadata, giữ generation span chỉ cho LLM; alert P95 latency đã cấu hình phải dẫn triage sang trace và log có correlation ID hợp lệ; thêm test concurrency cho `rag_slow` vào release check.
