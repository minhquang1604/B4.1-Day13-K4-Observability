# CP3 Challenge — Load Test & Metrics Evidence

Captured 2026-08-11 by Thành viên E (QA & Chief Investigator), local run (no Docker).

## 1. Baseline (before incident), practice traffic (`python scripts/load_test.py`)

Client-observed latency per request: 202.4ms, 159.7ms, 160.0ms, 156.6ms, 157.1ms, 157.5ms, 158.5ms, 157.1ms, 156.5ms, 155.0ms.

`GET /metrics` snapshot:

```json
{"traffic":10,"latency_p50":151.0,"latency_p95":151.0,"latency_p99":151.0,"avg_cost_usd":0.0021,"total_cost_usd":0.0206,"tokens_in_total":330,"tokens_out_total":1310,"error_breakdown":{},"quality_avg":0.88}
```

## 2. Incident injected (official challenge)

```text
$ python scripts/inject_incident.py
200 {'ok': True, 'incidents': {'rag_slow': True, 'tool_fail': False, 'cost_spike': False}}
```

## 3. Official challenge run (`python scripts/load_test.py --challenge --concurrency 5`)

Challenge: `day13-k4-observability-v1` | Cohort: K4

Client-observed (wall-clock, includes queueing) latency per request:

```text
[200] MISSING | monitoring | 7984.4ms
[200] MISSING | monitoring | 13300.1ms
[200] MISSING | monitoring | 13302.9ms
[200] MISSING | monitoring | 13302.5ms
[200] MISSING | monitoring | 13303.7ms
```

`GET /metrics` snapshot after the run (`latency_ms` here is measured server-side, inside `agent.run`, i.e. actual work time — not wall-clock/queue time):

```json
{"traffic":15,"latency_p50":151.0,"latency_p95":2659.0,"latency_p99":2659.0,"avg_cost_usd":0.002,"total_cost_usd":0.0305,"tokens_in_total":505,"tokens_out_total":1932,"error_breakdown":{},"quality_avg":0.8667}
```

## 4. Key discrepancy

Server-side `latency_ms` per request stayed ~2650ms (matches the 2.5s `retrieve()` sleep injected by `rag_slow` + ~150ms LLM call), while client-observed wall-clock latency for the same batch climbed to 7.9s–13.3s. See `cp3_challenge_logs.jsonl` — `request_received` timestamps for the 5 concurrent challenge queries are spaced ~2.65s apart (07:55:39.543, 07:55:42.202, 07:55:44.858, 07:55:47.522, 07:55:50.176) even though the load test fired all 5 at once with `--concurrency 5`. This spacing is the queueing/serialization signature, not the incident itself — see root cause analysis in `submission/REPORT.md` section 6.

## 5. Re-run after middleware/correlation-ID merge (2026-08-11, later same day)

Same flow (`inject_incident.py` → `load_test.py --challenge --concurrency 5` → `inject_incident.py --disable`), now on top of the merged correlation-ID middleware + log enrichment + `trace_id` field. Client-observed latency per request:

```text
[200] req-e7627862 | monitoring | 10687.3ms
[200] req-e0d52e9a | monitoring | 10686.7ms
[200] req-bf4302f5 | monitoring | 13348.2ms
[200] req-d34a0424 | monitoring | 13347.3ms
[200] req-0dabbc01 | monitoring | 13342.5ms
```

`GET /metrics` after the run:

```json
{"traffic":15,"latency_p50":150.0,"latency_p95":2657.0,"latency_p99":2657.0,"avg_cost_usd":0.0021,"total_cost_usd":0.0311,"tokens_in_total":505,"tokens_out_total":1972,"error_breakdown":{},"quality_avg":0.8667}
```

Same queueing/serialization symptom reproduces identically — confirms it's a structural property of `app/main.py`'s blocking `agent.run()` call inside `async def chat`, not a fluke of the first run. The refreshed `cp3_challenge_logs.jsonl` now links each pair by a real `correlation_id` (e.g. `req-e7627862`) instead of by timestamp, and carries full context (`user_id_hash`, `session_id`, `feature`, `model`, `env`) plus a `trace_id` field (currently `null` locally — `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` not set in this environment's `.env`).
