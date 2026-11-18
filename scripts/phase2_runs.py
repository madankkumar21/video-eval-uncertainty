"""The phase 2 runs (docs/PHASE2_PLAN.md): one row per run, shared by the analysis and the spend gate.

`estimate` is the plan's list-price cost for the run in USD. `flags` are the engines.plain flags
beyond --model, --n and --run-id. Ordering 0 of every permutation set is the existing phase 1 run
(`<model>-action_count-n100`), so it has no row here.
"""

from __future__ import annotations

MODEL_IDS = {
    "haiku45": "claude-haiku-4-5-20251001",
    "sonnet55": "claude-sonnet-5-5",
    "opus55": "claude-opus-5-5",
}
LABELS = {"haiku45": "Haiku 4.5", "sonnet55": "Sonnet 5.5", "opus55": "Opus 5.5"}

BUDGET_CAP_USD = 30.0       # pre-registered: under $30 more API spend in phase 2
OVERRUN_FACTOR = 1.5        # a finished run costing more than this times its estimate is a STOP


def run_id(model: str, suffix: str) -> str:
    return f"{model}-action_count-{suffix}"


def perm_run_id(model: str, k: int) -> str:
    return run_id(model, "n100") if k == 0 else run_id(model, f"n100-perm{k}")


PER_ITEM = {"haiku45": 0.004, "sonnet55": 0.008, "opus55": 0.017}  # plan's 8-frame list price per item

PHASE2_RUNS: list[dict] = []


def _add(step: str, model: str, suffix: str, n: int, flags: list[str], estimate: float, env: str = "") -> None:
    PHASE2_RUNS.append({"step": step, "model": model, "run_id": run_id(model, suffix), "n": n,
                        "flags": flags, "estimate": round(estimate, 3), "env": env})


# Step 2: blind baselines, text only. The plan says about $0.10 for all six; that undercounts Opus,
# which thinks before answering (phase 1: about 82 output tokens per item vs 9 for Haiku).
# Per run, assuming up to 400 input tokens per text-only call and phase 1's output tokens per item:
# Haiku 100 x (400 x $1 + 9 x $5)/1M, Sonnet 100 x (400 x $2 + 10 x $10)/1M, Opus 100 x (400 x $4 + 82 x $20)/1M.
BLIND_ESTIMATE = {"haiku45": 0.045, "sonnet55": 0.09, "opus55": 0.33}
for m in MODEL_IDS:
    _add("blind", m, "n100-blind", 100, ["--blind"], BLIND_ESTIMATE[m])
    _add("blind", m, "n100-blind-vshuf1", 100, ["--blind", "--value-shuffle-seed", "1"], BLIND_ESTIMATE[m])

# Steps 3-4: orderings 1-5 for Haiku and Sonnet
for m in ("haiku45", "sonnet55"):
    for k in range(1, 6):
        _add(f"perm-{m}", m, f"n100-perm{k}", 100, ["--permutation", str(k)], 100 * PER_ITEM[m])

# Step 5: frames 4 and 16 for Haiku (plan: $1.0 for both; 16 frames costs about twice 8)
_add("frames", "haiku45", "n100-f4", 100, ["--frames", "4"], 0.2)
_add("frames", "haiku45", "n100-f16", 100, ["--frames", "16"], 0.8)

# Step 6: items 101-200, original order, Haiku and Sonnet (plan: $1.2)
for m in ("haiku45", "sonnet55"):
    _add("items-101-200", m, "s100-n100", 100, ["--start", "100"], 100 * PER_ITEM[m])

# Step 8: Opus orderings 1-5 (plan: $8.5)
for k in range(1, 6):
    _add("perm-opus55", "opus55", f"n100-perm{k}", 100, ["--permutation", str(k)], 1.7)

# Step 9: Opus repeat of ordering 0 with the cache off (sampling variance), last
_add("opus-repeat", "opus55", "n100-rep2", 100, [], 1.7, env="VEU_CACHE=off")

# Step 7 (lmms-eval parity) runs outside this pipeline; its cost is tracked by hand.
PARITY_ESTIMATE = 1.0  # smoke test: ~9,600 input tokens per item, not 3,900


def total_estimate() -> float:
    return round(sum(r["estimate"] for r in PHASE2_RUNS) + PARITY_ESTIMATE, 2)
