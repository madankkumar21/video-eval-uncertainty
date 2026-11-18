"""Phase 2 spend gate: billed cost per run against its estimate and the pre-registered $30 cap.

Usage: uv run python scripts/phase2_spend.py                 # status of every phase 2 run
       uv run python scripts/phase2_spend.py --next <run_id>  # gate before starting <run_id>
       uv run python scripts/phase2_spend.py --next lmms-parity   # gate before the lmms-eval parity run

The lmms-eval parity spend is read from results/validation/parity_diff.json (written by
scripts/parity_diff.py from lmms-eval's logged token counts); --parity overrides it.

Exit codes: 0 = go; 2 = STOP (a finished run cost more than 1.5x its estimate, or the next run's
estimate would take cumulative phase 2 spend past the cap).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import RESULTS_DIR  # noqa: E402
from phase2_runs import BUDGET_CAP_USD, OVERRUN_FACTOR, PARITY_ESTIMATE, PHASE2_RUNS, total_estimate  # noqa: E402

PARITY_RUN = "lmms-parity"


def billed(run_id: str, results_dir: Path = RESULTS_DIR) -> float | None:
    p = results_dir / f"{run_id}.summary.json"
    if not p.exists():
        return None
    return float(json.loads(p.read_text())["cost_usd"])


def parity_cost(results_dir: Path = RESULTS_DIR) -> float | None:
    p = results_dir / "validation" / "parity_diff.json"
    if not p.exists():
        return None
    return float(json.loads(p.read_text()).get("cost_usd", 0.0))


def gate(next_run: str | None = None, parity: float | None = None, results_dir: Path = RESULTS_DIR) -> tuple[int, list[str]]:
    """Return (exit_code, report lines). parity=None reads the parity spend from parity_diff.json."""
    lines, stop = [], []
    if parity is None:
        parity = parity_cost(results_dir) or 0.0
    spent = parity
    lines.append(f"{'run':42s} {'estimate':>9s} {'billed':>9s}")
    for r in PHASE2_RUNS:
        b = billed(r["run_id"], results_dir)
        lines.append(f"{r['run_id']:42s} {r['estimate']:9.3f} {'-' if b is None else f'{b:9.3f}':>9s}")
        if b is not None:
            spent += b
            if b > OVERRUN_FACTOR * r["estimate"]:
                stop.append(f"{r['run_id']} cost ${b:.3f}, more than {OVERRUN_FACTOR}x its ${r['estimate']:.3f} estimate")
    if parity:
        lines.append(f"{'lmms-eval parity':42s} {PARITY_ESTIMATE:9.3f} {parity:9.3f}")
        if parity > OVERRUN_FACTOR * PARITY_ESTIMATE:
            stop.append(f"lmms-eval parity cost ${parity:.3f}, more than {OVERRUN_FACTOR}x its ${PARITY_ESTIMATE:.3f} estimate")
    lines.append(f"phase 2 spent ${spent:.2f} of the ${BUDGET_CAP_USD:.0f} cap; plan total ${total_estimate():.2f}")
    if next_run == PARITY_RUN:
        if spent + PARITY_ESTIMATE > BUDGET_CAP_USD:
            stop.append(f"lmms-eval parity (est ${PARITY_ESTIMATE:.2f}) would take spend past the cap")
        else:
            lines.append(f"next: lmms-eval parity, est ${PARITY_ESTIMATE:.2f}; spend after it about ${spent + PARITY_ESTIMATE:.2f}")
    elif next_run is not None:
        row = next((r for r in PHASE2_RUNS if r["run_id"] == next_run), None)
        if row is None:
            stop.append(f"{next_run} is not a phase 2 run (see scripts/phase2_runs.py)")
        elif billed(next_run, results_dir) is not None:
            lines.append(f"{next_run} already has a summary; rerunning it re-uses the cache and should cost about $0")
        elif spent + row["estimate"] > BUDGET_CAP_USD:
            stop.append(f"{next_run} (est ${row['estimate']:.2f}) would take spend to ${spent + row['estimate']:.2f}, past the cap")
        else:
            lines.append(f"next: {next_run}, est ${row['estimate']:.2f}; spend after it about ${spent + row['estimate']:.2f}")
    for s in stop:
        lines.append(f"STOP: {s}")
    lines.append("GO" if not stop else "STOP")
    return (2 if stop else 0), lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--next", default=None)
    ap.add_argument("--parity", type=float, default=None, help="override the lmms-eval parity spend in USD")
    a = ap.parse_args()
    code, lines = gate(a.next, a.parity)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
