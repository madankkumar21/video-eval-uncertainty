#!/usr/bin/env bash
# Replays Temporal scenarios 1-3 with the core cache off and prints API-call counts.
# Needs: temporal server start-dev --db-filename results/temporal.db  (already running)
# Background processes start from .venv/bin/python, not `uv run`: uv spawns python as a child, so
# kill -9 on the uv PID leaves python running and the "crash" never happens. Run `uv sync` first.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results
STAMP=$(date +%H%M%S)

PY=.venv/bin/python
calls_for_run() { sqlite3 results/cache.sqlite "SELECT COUNT(*) FROM http_calls WHERE run_id='$1'"; }
pids_for_run() { sqlite3 results/cache.sqlite "SELECT COUNT(DISTINCT pid) FROM http_calls WHERE run_id='$1'"; }
kill_and_check() {
  kill -9 "$1" 2>/dev/null || true; sleep 1
  # A dead child can linger as a zombie until reaped, and kill -0 still succeeds on it; check the state instead.
  state=$(ps -o stat= -p "$1" 2>/dev/null | tr -d ' ' || true)   # ps exits 1 once the PID is gone; don't let set -e abort here
  case "$state" in ""|Z*) ;; *) echo "FATAL: PID $1 survived kill -9 (state $state)" >&2; exit 1;; esac
  echo "killed PID $1 (confirmed gone)"
}
start_worker() {
  VEU_CACHE=off VEU_STUB_DELAY_S=1 VEU_FAIL_ITEM=action_count:video_7958 \
    nohup "$PY" -m engines.temporal_app.worker >> results/worker.log 2>&1 &
  echo $! > results/worker.pid; sleep 6
}
stop_worker() { kill_and_check "$(cat results/worker.pid)"; }

rm -f results/.fault-* 2>/dev/null || true
start_worker

echo "== S1: item 2 raises a simulated 429 once; Temporal retries =="
uv run python -m engines.temporal_app.run start --run-id "s1-$STAMP" --model stub --n 10 >/dev/null
sleep 18
uv run python -m engines.temporal_app.run approve --run-id "s1-$STAMP" --decision yes --wait | grep -E '"published"|"correct"'
grep "s1-$STAMP" results/worker.log | grep "attempt" | head -3
echo "calls: $(calls_for_run "s1-$STAMP") for 10 items"

echo; echo "== S2: kill -9 the worker mid-run, restart, resume =="
uv run python -m engines.temporal_app.run start --run-id "s2-$STAMP" --model stub --n 30 >/dev/null
sleep 9
echo "calls before kill: $(calls_for_run "s2-$STAMP")"
stop_worker; echo "worker killed"; sleep 2
uv run python -m engines.temporal_app.run status --run-id "s2-$STAMP" | head -1
start_worker; echo "worker restarted"; sleep 32
uv run python -m engines.temporal_app.run approve --run-id "s2-$STAMP" --decision yes --wait | grep -E '"published"|"n"'
echo "calls after resume: $(calls_for_run "s2-$STAMP") for 30 items; distinct worker PIDs: $(pids_for_run "s2-$STAMP")"

echo; echo "== S2 baseline: plain loop, cache off, killed at the same point =="
( VEU_CACHE=off VEU_STUB_DELAY_S=1 "$PY" -m engines.plain --model stub --n 30 --run-id "plain-$STAMP" --yes >/dev/null 2>&1 & echo $! > results/plain.pid )
sleep 9; kill_and_check "$(cat results/plain.pid)"
echo "calls before kill: $(calls_for_run "plain-$STAMP")"
VEU_CACHE=off VEU_STUB_DELAY_S=1 "$PY" -m engines.plain --model stub --n 30 --run-id "plain-$STAMP" --yes >/dev/null 2>&1
echo "calls after restart: $(calls_for_run "plain-$STAMP") for 30 items; distinct PIDs: $(pids_for_run "plain-$STAMP")"

echo; echo "== S3 is the approve step above: the run waited in RUNNING until signalled =="
stop_worker
