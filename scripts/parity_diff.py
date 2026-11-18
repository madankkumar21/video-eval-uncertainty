"""Item-level diff of an lmms-eval MVBench run against one of this pipeline's runs (H6).

Reads the per-sample log lmms-eval writes with --log_samples (`<date>_samples_mvbench_action_count.jsonl`),
matches items by video name, or by `doc_id` (file order) when the log has no `doc` (0.7.3 writes none),
and compares with our run's pred_letter.

Two parses of each reply are kept:
- `letter`: strict. The reply must open with the option letter ("B", "(B)", "B. 4"). A reply that hit
  the generation cap (output tokens >= --max-new-tokens) counts as unparsed. Agreement uses this one.
- `lmms_letter`: a port of lmms-eval's own mvbench mcq_acc, which takes the first standalone A-E in
  free text, so the article "a" in a cut-off sentence reads as option A. Reported to show how
  lmms-eval itself would have scored the reply.

Usage: uv run python scripts/parity_diff.py <lmms samples .jsonl> [--run haiku45-action_count-n100]
Writes results/validation/parity_diff.json and prints the summary, including the lmms-eval calls'
list-price cost from their logged token counts (enter it with phase2_spend.py --parity).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import RESULTS_DIR  # noqa: E402
from core.model import PRICES  # noqa: E402
from core.publish import load_run  # noqa: E402

_STRICT_RE = re.compile(r"^\(?([A-E])\)?(?:[.):]|\s|$)")
_OPTION_RE = re.compile(r"^([A-E])\.\s*(.+)$", re.IGNORECASE)
_LETTER_RE = re.compile(r"\b([A-E])\b", re.IGNORECASE)
_PUNCT = [";", r"/", "[", "]", '"', "{", "}", "(", ")", "=", "+", "\\", "_", "-", ">", "<", "@", "`", ",", "?", "!"]


def lmms_letter(text: str) -> str | None:
    """Answer letter per a port of lmms-eval 0.7.3 mvbench mcq_acc's extraction (A-E), or None."""
    m = _OPTION_RE.match(text.strip())
    if m:
        return m.group(1).upper()
    s = text.replace("\n", " ").replace("\t", " ").strip()
    for p in _PUNCT:
        s = s.replace(p, " ")
    s = s.strip().strip("'\"()").strip()
    m = _LETTER_RE.search(s)
    return m.group(1).upper() if m else None


def strict_letter(text: str) -> str | None:
    """The option letter only when the reply opens with it; None for free text."""
    m = _STRICT_RE.match(text.strip())
    return m.group(1) if m else None


def _response_text(sample: dict) -> str:
    r = sample.get("filtered_resps") or sample.get("resps") or [""]
    while isinstance(r, list):
        r = r[0] if r else ""
    return str(r)


def _tokens(sample: dict) -> tuple[int, int]:
    tin = tout = 0
    for tc in sample.get("token_counts") or []:
        if tc:
            tin += int(tc.get("input_tokens") or 0)
            tout += int(tc.get("output_tokens") or 0)
    return tin, tout


def _item_ids_by_doc_id(task: str, n: int) -> list[str]:
    from core.tasks import load_items  # needs json/<task>.json, i.e. dataset access, on first use
    return [it.item_id for it in load_items(task, n)]


def diff(samples_path: Path, run: str, task: str = "action_count", model: str = "claude-haiku-4-5-20251001",
         max_new_tokens: int = 16, item_ids: list[str] | None = None) -> dict:
    """item_ids: item ids in file order, for logs without `doc`; loaded from the dataset when needed."""
    ours = {r["item_id"]: r for r in load_run(run)}
    samples = [json.loads(x) for x in samples_path.read_text().splitlines() if x.strip()]
    if any("doc" not in s for s in samples) and item_ids is None:
        item_ids = _item_ids_by_doc_id(task, max(int(s["doc_id"]) for s in samples) + 1)
    rows = []
    tin = tout = 0
    for s in samples:
        a, b = _tokens(s)
        tin, tout = tin + a, tout + b
        if "doc" in s:
            item_id = f"{task}:{Path(s['doc']['video']).stem}"
        else:
            item_id = item_ids[int(s["doc_id"])]
        text = _response_text(s)
        truncated = b >= max_new_tokens
        rows.append({"item_id": item_id, "lmms_text": text, "truncated": truncated,
                     "letter": None if truncated else strict_letter(text), "lmms_letter": lmms_letter(text),
                     "ours": ours[item_id]["pred_letter"] if item_id in ours else None, "in_ours": item_id in ours})
    common = [r for r in rows if r["in_ours"]]
    agree = sum(1 for r in common if r["letter"] is not None and r["letter"] == r["ours"])
    p_in, p_out = PRICES[model]
    return {"run": run, "samples": str(samples_path), "n": len(common), "agree": agree,
            "input_tokens": tin, "output_tokens": tout, "cost_usd": round((tin * p_in + tout * p_out) / 1e6, 4),
            "unparsed": sum(1 for r in common if r["letter"] is None),
            "truncated": sum(1 for r in common if r["truncated"]),
            "lmms_unparsed": sum(1 for r in common if r["lmms_letter"] is None),
            "lmms_reads_free_text_as_letter": sum(1 for r in common if r["letter"] is None and r["lmms_letter"] is not None),
            "not_in_run": len(rows) - len(common),
            "disagreements": [r for r in common if r["letter"] != r["ours"]]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("samples")
    ap.add_argument("--run", default="haiku45-action_count-n100")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001", help="for the list-price cost of the lmms-eval calls")
    ap.add_argument("--max-new-tokens", type=int, default=16, help="the task's generation cap; a reply that reaches it is truncated")
    a = ap.parse_args()
    out = diff(Path(a.samples), a.run, model=a.model, max_new_tokens=a.max_new_tokens)
    dest = RESULTS_DIR / "validation" / "parity_diff.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    print(f"agree {out['agree']}/{out['n']}; unparsed {out['unparsed']} (truncated {out['truncated']}); "
          f"free text lmms-eval would still score as a letter: {out['lmms_reads_free_text_as_letter']}; "
          f"samples not in {a.run}: {out['not_in_run']}; lmms-eval tokens {out['input_tokens']} in / "
          f"{out['output_tokens']} out = ${out['cost_usd']:.4f} at list price; wrote {dest}")


if __name__ == "__main__":
    main()
