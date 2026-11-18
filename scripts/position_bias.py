"""Compare an unshuffled run with a shuffled run of the same model on the same items.

Three questions:
  1. Pick distribution: does the model keep choosing the same *position* when the options move?
  2. Content consistency: on how many items did it choose the same *answer text* in both runs?
     A model that is counting picks the same number regardless of where it sits.
  3. Accuracy: paired comparison (McNemar + bootstrap) between the two runs.

Usage: uv run python scripts/position_bias.py <run_a> <run_b> [--seed 1]
       (omit --seed when run_b used the original option order, e.g. a numbered-label or second-model run)
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.publish import load_run  # noqa: E402
from core.stats import compare_runs, wilson  # noqa: E402
from core.tasks import LETTERS, load_items  # noqa: E402


def chosen_text(row: dict, item) -> str | None:
    if row["pred_letter"] is None:
        return None
    return item.candidates[LETTERS.index(row["pred_letter"])]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("--seed", type=int, default=None, help="shuffle seed used for run_b (omit if run_b was unshuffled)")
    ap.add_argument("--task", default="action_count")
    a = ap.parse_args()

    rows_a = {r["item_id"]: r for r in load_run(a.run_a)}
    rows_b = {r["item_id"]: r for r in load_run(a.run_b)}
    n = max(len(rows_a), len(rows_b))
    items_a = {it.item_id: it for it in load_items(a.task, n)}
    items_b = {it.item_id: it for it in load_items(a.task, n, shuffle_seed=a.seed)}
    common = [i for i in rows_a if i in rows_b]

    print(f"items in both runs: {len(common)}\n")

    for label, rows, items in (("unshuffled", rows_a, items_a), ("shuffled", rows_b, items_b)):
        picks = Counter(rows[i]["pred_letter"] for i in common)
        truth = Counter(items[i].answer_letter for i in common)
        k = sum(rows[i]["correct"] for i in common)
        w = wilson(k, len(common))
        by_pos = {}
        for L in "ABC":
            ids = [i for i in common if items[i].answer_letter == L]
            by_pos[L] = f"{sum(rows[i]['correct'] for i in ids)}/{len(ids)}"
        print(f"{label:11s} acc {w.acc:.1%} [{w.lo:.1%}, {w.hi:.1%}]  "
              f"picks A/B/C = {picks['A']}/{picks['B']}/{picks['C']}  "
              f"correct positions A/B/C = {truth['A']}/{truth['B']}/{truth['C']}  "
              f"acc by correct position {by_pos}")

    same_text = sum(chosen_text(rows_a[i], items_a[i]) == chosen_text(rows_b[i], items_b[i]) for i in common)
    same_letter = sum(rows_a[i]["pred_letter"] == rows_b[i]["pred_letter"] for i in common)
    moved = sum(items_a[i].candidates != items_b[i].candidates for i in common)
    print(f"\noption order changed on {moved}/{len(common)} items")
    print(f"same answer TEXT in both runs:   {same_text}/{len(common)}  (counting would make this high)")
    print(f"same answer LETTER in both runs: {same_letter}/{len(common)}  (position bias would make this high)")

    cmp = compare_runs([rows_a[i] for i in common], [rows_b[i] for i in common])
    p = cmp["paired"]
    print(f"\npaired: diff (unshuffled - shuffled) {p['diff']:+.1%}, bootstrap [{p['boot_lo']:+.1%}, {p['boot_hi']:+.1%}], "
          f"discordant b={p['b']} c={p['c']}, McNemar p={p['p_mcnemar']:.3f}: {p['verdict']}")


if __name__ == "__main__":
    main()
