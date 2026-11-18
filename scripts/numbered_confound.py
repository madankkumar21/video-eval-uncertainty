"""Check the numbered-label confound: is the model returning a slot number, or a count?

On action_count the options are themselves counts, so with labels (1)/(2)/(3) a returned "2"
could mean "the second option" or "the count is two". RESULTS.md reports four figures from
this check; this script recomputes them from the option texts (needs json/action_count.json).

  1. returned label equals the true count
  2. returned label equals any option text
  3. items where "2" is one of the options
  4. among items whose true count is 3: how often the model returned "2", and "3"

Usage: uv run python scripts/numbered_confound.py [run_id] [--task action_count]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.publish import load_run  # noqa: E402
from core.tasks import LETTERS, load_items  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", default="haiku45-action_count-n100-numbered")
    ap.add_argument("--task", default="action_count")
    a = ap.parse_args()

    rows = {r["item_id"]: r for r in load_run(a.run)}
    items = {it.item_id: it for it in load_items(a.task, len(rows))}
    ids = [i for i in rows if i in items]
    n = len(ids)

    def label(i: str) -> str | None:
        p = rows[i]["pred_letter"]
        return None if p is None else str(LETTERS.index(p) + 1)

    def norm(s: str) -> str:
        return s.strip().rstrip(".").lower()

    match_true = sum(label(i) == norm(items[i].answer) for i in ids)
    match_any = sum(label(i) in {norm(c) for c in items[i].candidates} for i in ids)
    two_is_option = sum("2" in {norm(c) for c in items[i].candidates} for i in ids)
    true3 = [i for i in ids if norm(items[i].answer) == "3"]
    ret_on_true3 = Counter(label(i) for i in true3)

    print(f"run {a.run}: {n} items")
    print(f"answer texts seen: {sorted({norm(items[i].answer) for i in ids})}")
    print(f"1. returned label == true count:        {match_true}/{n}   (RESULTS.md says 8/100)")
    print(f"2. returned label == any option text:   {match_any}/{n}   (RESULTS.md says 37/100)")
    print(f"3. '2' is one of the options:           {two_is_option}/{n}   (RESULTS.md says 52)")
    print(f"4. true count 3: {len(true3)} items; returned '2' on {ret_on_true3['2']}, '3' on {ret_on_true3['3']}"
          f"   (RESULTS.md says 41 items, '2' on 36, '3' once)")


if __name__ == "__main__":
    main()
