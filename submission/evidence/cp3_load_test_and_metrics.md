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
