"""Position-bias and baseline metrics for multiple-choice runs. Plain functions, no engine, no I/O.

Inputs are plain lists so the metrics can be tested without the dataset:
- a permutation set is a matrix indexed [item][ordering], one column per option ordering;
- picks are letters by position ("A", "B", ...) or None for a parse failure.

References: MMBench CircularEval (consistency, correct under every ordering); PriDe and
"content-free" prompting (a no-evidence prior); Cramér (1946) for V.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from scipy.stats import binomtest, chi2_contingency, chisquare

from .stats import wilson


def _wilson_dict(k: int, n: int) -> dict:
    w = wilson(k, n)
    return {"k": k, "n": n, "acc": w.acc, "lo": w.lo, "hi": w.hi}


def majority_baseline(values: list[str]) -> dict:
    """Score of always giving the most common value (an answer text, or a slot letter)."""
    if not values:
        return {"value": None, **_wilson_dict(0, 0)}
    value, k = Counter(values).most_common(1)[0]
    return {"value": value, **_wilson_dict(k, len(values))}


def perm_averaged_accuracy(correct: list[list[bool]], n_boot: int = 10_000, seed: int = 0,
                           alpha: float = 0.05) -> dict:
    """Mean accuracy over every ordering, with a bootstrap interval that resamples items.

    correct[i][p] is whether item i was answered correctly under ordering p. Items are the
    resampling unit because the orderings of one item share a video and are not independent.
    """
    m = np.asarray(correct, dtype=float)
    if m.size == 0:
        return {"acc": float("nan"), "lo": float("nan"), "hi": float("nan"), "per_ordering": [], "n_items": 0}
    per_item = m.mean(axis=1)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(per_item), size=(n_boot, len(per_item)))
    boots = per_item[idx].mean(axis=1)
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return {"acc": float(per_item.mean()), "lo": float(lo), "hi": float(hi),
            "per_ordering": [float(x) for x in m.mean(axis=0)], "n_items": int(m.shape[0]),
            "n_orderings": int(m.shape[1])}


def consistency(chosen_content: list[list[str | None]], correct: list[list[bool]] | None = None) -> dict:
    """Share of items where the same answer text was chosen under every ordering.

    With `correct`, also the CircularEval score: share of items answered correctly under every
    ordering. A parse failure under any ordering counts as inconsistent.
    """
    n = len(chosen_content)
    same = sum(1 for row in chosen_content if row and None not in row and len(set(row)) == 1)
    out = {"consistency": _wilson_dict(same, n)}
    if correct is not None:
        circ = sum(1 for row in correct if row and all(row))
        out["circular_accuracy"] = _wilson_dict(circ, n)
    return out


def cramers_v_position(chosen_slots: list[list[int | None]], n_options: int) -> dict:
    """Cramér's V between slot and being chosen, over every item x ordering x slot cell.

    Each answered (item, ordering) contributes n_options cells, one chosen. Over a full set of
    orderings every option sits in every slot equally often, so a model that ignores position
    chooses each slot a third of the time and V = 0. Always choosing one slot gives V = 1.
    On a single ordering the same number measures slot preference against uniform, not against
    where the answers are. The p-value is a goodness-of-fit test of chosen-slot counts against
    uniform (the cells within one item x ordering are not independent, so the 3x2 table's own
    chi-square p-value would overstate significance).
    """
    picks = [s for row in chosen_slots for s in row if s is not None]
    counts = [sum(1 for s in picks if s == j) for j in range(n_options)]
    total = len(picks)
    if total == 0:
        return {"v": float("nan"), "p": float("nan"), "slot_counts": counts, "n_picks": 0}
    table = [[c, total - c] for c in counts]  # rows: slot; columns: chosen, not chosen
    chi2 = chi2_contingency(table, correction=False).statistic
    v = float(np.sqrt(chi2 / (total * n_options)))  # N = total * n_options cells; min(rows, cols) - 1 = 1
    p = float(chisquare(counts).pvalue)
    return {"v": v, "p": p, "slot_counts": counts, "n_picks": total}


def blind_prior(picks: list[str | None], candidates: list[tuple[str, ...]], value: str | None = None) -> dict:
    """What a model picks with no evidence: share per slot, and share of picks equal to `value`.

    `value` is the slice's majority answer (e.g. "3"). On a value-shuffled run that keeps `value`
    out of the middle slot, middle picks and value picks are disjoint; the binomial test asks
    which of the two the model prefers, over items where it picked one of them.
    """
    letters = "ABCDEFGHIJ"
    n = len(picks)
    n_opt = len(candidates[0]) if candidates else 0
    answered = [p for p in picks if p is not None]
    slot = {letters[j]: _wilson_dict(sum(1 for p in answered if p == letters[j]), n) for j in range(n_opt)}
    out: dict = {"n": n, "parse_failures": n - len(answered), "slot_share": slot}
    if value is None:
        return out
    chose_value = [p is not None and candidates[i][letters.index(p)] == value for i, p in enumerate(picks)]
    out["value"] = value
    out["value_share"] = _wilson_dict(sum(chose_value), n)
    if n_opt % 2 == 1:
        mid = letters[n_opt // 2]
        # items where the value is present and not in the middle: middle and value are disjoint
        sep = [i for i in range(n) if value in candidates[i] and candidates[i][n_opt // 2] != value]
        m_ct = sum(1 for i in sep if picks[i] == mid)
        v_ct = sum(1 for i in sep if chose_value[i])
        bt = binomtest(m_ct, m_ct + v_ct, 0.5) if m_ct + v_ct else None
        out["middle_share"] = slot[mid]
        out["separated"] = {"items": len(sep), "middle": m_ct, "value": v_ct,
                            "p_binomial": float(bt.pvalue) if bt else None}
    return out


def cost_per_correct(rows: list[dict], prices: dict[str, tuple[float, float]]) -> dict:
    """Cost per correct answer from list prices on every call's tokens, so cache hits don't flatter it.

    Billed cost (what this run paid, cache hits at $0) is reported alongside.
    """
    n = len(rows)
    correct = sum(1 for r in rows if r["correct"])
    uncached = 0.0
    for r in rows:
        p_in, p_out = prices.get(r["model_id"], (0.0, 0.0))
        uncached += (r["input_tokens"] * p_in + r["output_tokens"] * p_out) / 1e6
    billed = sum(r["cost_usd"] for r in rows)
    return {"n": n, "correct": correct, "cost_uncached": round(uncached, 4), "cost_billed": round(billed, 4),
            "cost_per_100_items": round(100 * uncached / n, 4) if n else None,
            "cost_per_correct": round(uncached / correct, 5) if correct else None}


def paired_vs_baseline(correct: list[list[bool]], baseline_correct: list[bool], n_boot: int = 10_000,
                       seed: int = 0, alpha: float = 0.05) -> dict:
    """Permutation-averaged accuracy minus a baseline's accuracy on the same items, item bootstrap.

    correct[i][p] is the model's correctness on item i under ordering p; baseline_correct[i] is
    whether the baseline (e.g. "always answer 3") is right on item i. Both sides are resampled
    together, so the interval accounts for the uncertainty in each and for their correlation.
    """
    m = np.asarray(correct, dtype=float).mean(axis=1)
    b = np.asarray(baseline_correct, dtype=float)
    d = m - b
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    boots = d[idx].mean(axis=1)
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return {"diff": float(d.mean()), "lo": float(lo), "hi": float(hi), "n_items": int(len(d)),
            "distinguishable": bool(lo > 0 or hi < 0)}
