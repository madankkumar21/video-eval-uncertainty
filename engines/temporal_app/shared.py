"""Dataclasses that cross the workflow/activity boundary. Plain data only; no frames, no numpy."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalParams:
    run_id: str
    model_id: str = "stub"
    task: str = "action_count"
    n: int = 100
    n_frames: int = 8
    shuffle_seed: int | None = None
    label_style: str = "letter"
    chunk: int = 200              # continue-as-new after this many items (scenario 5)
    start_index: int = 0          # carried across continue-as-new
    rows: list[dict] = field(default_factory=list)  # Scored rows so far, carried across continue-as-new


@dataclass
class ItemCall:
    run_id: str
    model_id: str
    task: str
    index: int                    # position in load_items(task) order; ids are re-derived in the activity
    n_frames: int
    shuffle_seed: int | None = None
    label_style: str = "letter"


@dataclass
class RunSummary:
    model_id: str
    n: int
    correct: int
    accuracy: float
    wilson_lo: float
    wilson_hi: float
    cost_usd: float
    cached_items: int
    parse_failures: int
