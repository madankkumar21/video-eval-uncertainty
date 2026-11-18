# The same run on each engine

Workload: MVBench `action_count`, stub model with a 1-second delay per call, core cache **off** (`VEU_CACHE=off`) so what you see is the engine, not my cache. "API calls" are rows in the `http_calls` table for that run id; every real call costs money, so the count is the bill.

| # | Scenario | Plain loop | Temporal |
|---|---|---|---|
| 1 | A model call raises a rate-limit error | Hand-written `while True` with `sleep(2**attempt)` in `engines/plain.py` | `RetryPolicy(initial 2s, x2, max 60s, 8 attempts, non_retryable=["Fatal"])` on the activity. Item 2 failed on attempt 1 and completed on attempt 2; the workflow never saw the error. |
| 2 | Worker killed with `kill -9` mid-run, then restarted (30 items, killed after 6 to 8) | Restarted from item 1. **36 calls for 30 items** (6 before the kill, then all 30 again), 2 distinct PIDs. The core cache (on by default) is the only thing that saves the plain loop. | Resumed from the next item by replaying history. **30 calls for 30 items**, 2 distinct worker PIDs, kill confirmed by process state. At most one duplicate is possible if the kill lands inside an in-flight call. Needs `--db-filename` on the dev server or history dies with the server process. |
| 3 | A person must approve before results publish | `input()` blocks the process; kill it and the run is gone | `wait_condition` on an `approve` signal. The run sits in RUNNING with no worker attached and survives worker restarts. `status` query shows the summary while it waits. |
| 4 | Code changes while a run is in flight | nothing to break; nothing to protect | `workflow.patched()` hook not yet wired |
| 5 | A batch of thousands | memory and patience | `continue_as_new` every 200 items or when the server suggests it (hard limit 51,200 events; 100 items is about 600) |

## Runs behind the numbers (2026-10-04, after the kill-test fix)

The first version of this table (2026-10-03) killed the `uv run` wrapper, not python. uv spawns python as a child, so both the Temporal worker and the plain loop survived as orphans and the "crash" never happened. Those numbers ("30 vs 60") are withdrawn. `scripts/temporal_scenarios.sh` now launches `.venv/bin/python` directly, checks the process state after the kill, and reports distinct PIDs from the `http_calls` table.

```
S1  s1-*      attempt 1 failed (simulated 429), attempt 2 ok, published, 10 calls for 10 items
S2  s2-*      8 calls before kill -9 (confirmed gone), 30 calls total after resume, 2 worker PIDs, published
S2  plain-*   6 calls before kill -9 (confirmed gone), 36 calls total after restart, 2 PIDs
S3  s2-*      waited in RUNNING with no worker attached; approve=yes -> published
```

## What the comparison is and isn't

- The engines are compared on the same core code and the same items. Only the adapter changes.
- With the core cache on, every engine resumes without re-paying, including the plain loop. The cache-off runs show what the engine itself buys you. A fair claim is "the engine journals the result; the cache is belt and braces."
- Stub calls cost nothing. The call counts are what matters; with a real model each count costs about $0.004 on Haiku 4.5 and $0.008 on Sonnet 5.5.
