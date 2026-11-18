"""Analysis for the phase 1 reruns and the phase 2 runs. Every number in the write-up comes from here, not from hand arithmetic.

Usage: uv run python scripts/handoff_analysis.py            # prints the report
       uv run python scripts/handoff_analysis.py --json out.json

Sections:
  A. Per-run summary: accuracy, Wilson, picks, true positions, goodness-of-fit of picks vs true positions,
     accuracy-by-position chi-square, cost.
  B. Shuffle pairs: 3-way split over moved-choice items (followed text / same letter / third option),
     binomial test same-letter vs third, paired comparison.
  C. Repeat pairs (same prompt twice): same-letter agreement, discordance, paired comparison.
  D. Cross-model and condition pairs: paired comparison with single-flip fragility.
  E. Bonferroni over all paired tests reported in RESULTS.md.

Phase 2 (docs/PHASE2_PLAN.md, hypotheses H1-H6), each section skips runs that do not exist yet:
  F. Majority-label baselines on items 1-100 and 1-200.
  G. Blind prior (no frames): framed vs blind per model (H1), middle slot vs majority value (H2).
  H. Permutation sets (all 6 option orderings): permutation-averaged accuracy, consistency,
     CircularEval accuracy, Cramer's V for position dependence (H3).
  I. 200 items: original 1-100 joined to 101-200 (H4).
  J. Frames: 4 vs 16 frames for Haiku (H5).
  K. Harness parity with lmms-eval, read from results/validation/parity_diff.json (H6).
  L. Opus repeat of ordering 0 (sampling variance).
  M. Cost per correct answer for every run and permutation set.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, chi2_contingency, chisquare

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import RESULTS_DIR  # noqa: E402
from core.bias import (blind_prior, consistency, cost_per_correct, cramers_v_position,  # noqa: E402
                       majority_baseline, paired_vs_baseline, perm_averaged_accuracy)
from core.model import PRICES  # noqa: E402
from core.publish import load_run  # noqa: E402
from core.stats import compare_runs, mcnemar, wilson  # noqa: E402
from core.tasks import LETTERS, load_items  # noqa: E402

TASK = "action_count"
N = 100

RUNS = {
    # run_id: (label, shuffle_seed)
    "haiku45-action_count-n100": ("Haiku t=0", None),
    "haiku45-action_count-n100-rep2": ("Haiku t=0 repeat", None),
    "haiku45-action_count-n100-tdefault": ("Haiku default temp", None),
    "haiku45-action_count-n100-shuf1": ("Haiku t=0 shuffled", 1),
    "haiku45-action_count-n100-numbered": ("Haiku t=0 labels 1/2/3", None),
    "sonnet55-action_count-n100": ("Sonnet between_tools", None),
    "sonnet55-action_count-n100-rep2": ("Sonnet repeat", None),
    "sonnet55-action_count-n100-shuf1": ("Sonnet shuffled", 1),
    "opus55-action_count-n100": ("Opus medium effort", None),
    "opus55-action_count-n100-shuf1": ("Opus shuffled", 1),
}

SHUFFLE_PAIRS = [  # (unshuffled, shuffled)
    ("haiku45-action_count-n100", "haiku45-action_count-n100-shuf1"),
    ("sonnet55-action_count-n100", "sonnet55-action_count-n100-shuf1"),
    ("opus55-action_count-n100", "opus55-action_count-n100-shuf1"),
]
REPEAT_PAIRS = [
    ("haiku45-action_count-n100", "haiku45-action_count-n100-rep2"),
    ("sonnet55-action_count-n100", "sonnet55-action_count-n100-rep2"),
]
OTHER_PAIRS = [  # (A, B, label)
    ("haiku45-action_count-n100", "haiku45-action_count-n100-tdefault", "Haiku t=0 vs default temp"),
    ("haiku45-action_count-n100", "haiku45-action_count-n100-numbered", "Haiku letters vs numbers"),
    ("sonnet55-action_count-n100", "haiku45-action_count-n100", "Sonnet vs Haiku"),
    ("opus55-action_count-n100", "sonnet55-action_count-n100", "Opus vs Sonnet"),
    ("opus55-action_count-n100", "haiku45-action_count-n100", "Opus vs Haiku"),
]


def have(run_id: str) -> bool:
    return (RESULTS_DIR / f"{run_id}.jsonl").exists()


def rows_of(run_id: str) -> dict[str, dict]:
    return {r["item_id"]: r for r in load_run(run_id)}


def items_for(seed: int | None = None, **kw) -> dict:
    """Items keyed by item_id. kw: permutation, value_shuffle_seed, start, n (see core.tasks.load_items)."""
    return dict(_items(seed, tuple(sorted(kw.items()))))


@lru_cache(maxsize=None)
def _items(seed, kw_items):
    kw = dict(kw_items)
    n = kw.pop("n", N)
    return tuple((it.item_id, it) for it in load_items(TASK, n, shuffle_seed=seed, **kw))


def summary(run_id: str, label: str | None = None, item_kw: dict | None = None) -> dict:
    if label is None:
        label, seed = RUNS[run_id]
        item_kw = {"seed": seed}
    rows = rows_of(run_id)
    items = items_for(**(item_kw or {}))
    ids = list(rows)
    k = sum(rows[i]["correct"] for i in ids)
    w = wilson(k, len(ids))
    picks = Counter(rows[i]["pred_letter"] for i in ids)
    truth = Counter(items[i].answer_letter for i in ids)
    p_vec = [picks.get(L, 0) for L in "ABC"]
    t_vec = [truth.get(L, 0) for L in "ABC"]
    gof = chisquare(p_vec, f_exp=t_vec)
    # accuracy by correct position: 2x3 contingency (correct/incorrect x position)
    table = [[sum(rows[i]["correct"] for i in ids if items[i].answer_letter == L) for L in "ABC"],
             [sum(not rows[i]["correct"] for i in ids if items[i].answer_letter == L) for L in "ABC"]]
    chi = chi2_contingency(table)
    acc_by_pos = {L: f"{table[0][j]}/{table[0][j] + table[1][j]}" for j, L in enumerate("ABC")}
    cost = sum(rows[i]["cost_usd"] for i in ids)
    paid = sum(not rows[i]["cached"] for i in ids)
    parse_fail = sum(rows[i]["parse_failed"] for i in ids)
    return {
        "run_id": run_id, "label": label, "n": len(ids), "correct": k, "acc": w.acc, "lo": w.lo, "hi": w.hi,
        "picks_ABC": p_vec, "truth_ABC": t_vec, "gof_p": float(gof.pvalue),
        "acc_by_pos": acc_by_pos, "acc_by_pos_chi2_p": float(chi.pvalue),
        "cost_usd": round(cost, 4), "paid_calls": paid, "parse_failures": parse_fail,
    }


def paired(a_id: str, b_id: str, seed_b: int | None = None) -> dict:
    ra, rb = rows_of(a_id), rows_of(b_id)
    common = [i for i in ra if i in rb]
    cmp = compare_runs([ra[i] for i in common], [rb[i] for i in common])
    p = cmp["paired"]
    b, c = p["b"], p["c"]
    # single flip: move one discordant item from the larger side to the smaller
    if b >= c:
        fb, fc = b - 1, c + 1
    else:
        fb, fc = b + 1, c - 1
    flip_p = mcnemar(fb, fc)
    # same-letter agreement (meaningful when both runs show the same option order)
    same_letter = sum(ra[i]["pred_letter"] == rb[i]["pred_letter"] for i in common)
    return {
        "a": a_id, "b": b_id, "n": len(common), "diff": p["diff"], "boot_lo": p["boot_lo"], "boot_hi": p["boot_hi"],
        "b_discordant": b, "c_discordant": c, "p_mcnemar": p["p_mcnemar"], "verdict": p["verdict"],
        "flip_split": [fb, fc], "flip_p": flip_p,
        "flip_changes_verdict": (p["p_mcnemar"] < 0.05) != (flip_p < 0.05),
        "same_letter": same_letter, "discordant_total": b + c,
    }


def shuffle_split(unshuf_id: str, shuf_id: str, seed: int) -> dict:
    ra, rb = rows_of(unshuf_id), rows_of(shuf_id)
    ia, ib = items_for(None), items_for(seed)
    common = [i for i in ra if i in rb]

    def txt(r, it):
        return None if r["pred_letter"] is None else it.candidates[LETTERS.index(r["pred_letter"])]

    moved_choice = [i for i in common if ra[i]["pred_letter"] is not None
                    and ib[i].candidates.index(txt(ra[i], ia[i])) != LETTERS.index(ra[i]["pred_letter"])]
    followed = sum(txt(ra[i], ia[i]) == txt(rb[i], ib[i]) for i in moved_choice)
    same_letter = sum(ra[i]["pred_letter"] == rb[i]["pred_letter"] for i in moved_choice)
    third = len(moved_choice) - followed - same_letter
    # H3b-style test: same-letter vs third option, binomial against 0.5
    bt = binomtest(same_letter, same_letter + third, 0.5, alternative="greater") if same_letter + third else None
    orders_changed = sum(ia[i].candidates != ib[i].candidates for i in common)
    return {
        "unshuffled": unshuf_id, "shuffled": shuf_id, "orders_changed": orders_changed,
        "moved_choice_items": len(moved_choice), "followed_text": followed, "same_letter": same_letter,
        "third_option": third, "same_letter_vs_third_p": (float(bt.pvalue) if bt else None),
        "paired": paired(unshuf_id, shuf_id, seed),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--dump-items", action="store_true",
                    help="write results/validation/item_values.json (answer and options per item, items 1-200) so "
                         "figures that need option texts can be re-verified without the dataset")
    a = ap.parse_args()
    if a.dump_items:
        dump_item_values()
    out: dict = {"runs": {}, "shuffle": [], "repeat": [], "other": [], "missing": []}

    print("A. RUNS")
    for rid in RUNS:
        if not have(rid):
            out["missing"].append(rid)
            print(f"  (missing) {rid}")
            continue
        s = summary(rid)
        out["runs"][rid] = s
        print(f"  {s['label']:24s} {s['correct']:3d}/{s['n']} = {s['acc']:.0%} [{s['lo']:.1%}, {s['hi']:.1%}]  "
              f"picks {s['picks_ABC']} truth {s['truth_ABC']} gof p={s['gof_p']:.3g}  "
              f"acc-by-pos {s['acc_by_pos']} chi2 p={s['acc_by_pos_chi2_p']:.2f}  "
              f"${s['cost_usd']:.3f} ({s['paid_calls']} paid, {s['parse_failures']} parse fail)")

    print("\nB. SHUFFLE PAIRS (moved-choice split)")
    for u, s_ in SHUFFLE_PAIRS:
        if have(u) and have(s_):
            r = shuffle_split(u, s_, RUNS[s_][1])
            out["shuffle"].append(r)
            p = r["paired"]
            print(f"  {RUNS[u][0]:22s} orders changed {r['orders_changed']}; moved-choice {r['moved_choice_items']}: "
                  f"followed text {r['followed_text']}, same letter {r['same_letter']}, third {r['third_option']} "
                  f"(same-letter>third binomial p={r['same_letter_vs_third_p']:.3g}); "
                  f"acc diff {p['diff']:+.1%} boot [{p['boot_lo']:+.1%},{p['boot_hi']:+.1%}] b={p['b_discordant']} c={p['c_discordant']} "
                  f"p={p['p_mcnemar']:.3f} {p['verdict']}")

    print("\nC. REPEAT PAIRS (same prompt twice)")
    for a_, b_ in REPEAT_PAIRS:
        if have(a_) and have(b_):
            r = paired(a_, b_)
            out["repeat"].append(r)
            print(f"  {RUNS[a_][0]:22s} same letter {r['same_letter']}/{r['n']}; discordant on correctness "
                  f"b={r['b_discordant']} c={r['c_discordant']} (total {r['discordant_total']}); "
                  f"acc diff {r['diff']:+.1%} p={r['p_mcnemar']:.3f} {r['verdict']}")

    print("\nD. OTHER PAIRS (A vs B, with single-flip fragility)")
    for a_, b_, label in OTHER_PAIRS:
        if have(a_) and have(b_):
            r = paired(a_, b_)
            r["label"] = label
            out["other"].append(r)
            print(f"  {label:28s} diff {r['diff']:+.1%} boot [{r['boot_lo']:+.1%},{r['boot_hi']:+.1%}] "
                  f"b={r['b_discordant']} c={r['c_discordant']} p={r['p_mcnemar']:.3f} {r['verdict']}; "
                  f"one flip -> {r['flip_split']} p={r['flip_p']:.3f}"
                  f"{' CHANGES VERDICT' if r['flip_changes_verdict'] else ''}")

    tests = [x["paired"] for x in out["shuffle"]] + out["repeat"] + out["other"]
    m = len(tests)
    alpha = 0.05 / m if m else None
    out["bonferroni"] = {"tests": m, "alpha": alpha,
                         "survivors": [t.get("label", f"{t['a']} vs {t['b']}") for t in tests if alpha and t["p_mcnemar"] < alpha]}
    print(f"\nE. BONFERRONI: {m} paired tests, alpha = {alpha:.4f}; survivors: {out['bonferroni']['survivors'] or 'none'}" if m else "")

    total = sum(s["cost_usd"] for s in out["runs"].values())
    out["total_cost_usd"] = round(total, 3)
    print(f"\nTotal billed across listed runs: ${total:.3f}")

    out["phase2"] = phase2()
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2))



# ---------------------------------------------------------------- phase 2

def dump_item_values(n: int = 200) -> Path:
    """Answer and option values per item in file order, plus the value-shuffled order for items 1-100.

    Option values only (counts such as "3"); no question text, no video. Lets a session without
    dataset access recompute the majority baseline, H2's middle-vs-value split and H3's paired test.
    """
    base = items_for(n=n)
    vs = items_for(value_shuffle_seed=1)
    out = {i: {"answer": it.answer, "candidates": list(it.candidates),
               **({"vshuf1_candidates": list(vs[i].candidates)} if i in vs else {})} for i, it in base.items()}
    dest = RESULTS_DIR / "validation" / "item_values.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1))
    print(f"wrote {dest} ({len(out)} items)")
    return dest


sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase2_runs import LABELS, MODEL_IDS, perm_run_id, run_id  # noqa: E402

H1_ALPHA = 0.05 / 3          # pre-registered: Bonferroni over the three framed-vs-blind tests
H3_CONSISTENCY_MAX = {"haiku45": 0.50, "sonnet55": 0.75, "opus55": 0.75}
H5_MAX_POINTS = 0.05
H6_MIN_AGREE = 0.90


def _rows_list(run: str) -> list[dict]:
    return list(rows_of(run).values())


def _majority(n: int) -> dict:
    items = list(items_for(n=n).values())
    return {"value": majority_baseline([it.answer for it in items]),
            "slot": majority_baseline([it.answer_letter for it in items])}


def _blind(model: str, maj_value: str) -> dict | None:
    framed, blind, vshuf = run_id(model, "n100"), run_id(model, "n100-blind"), run_id(model, "n100-blind-vshuf1")
    if not have(blind):
        return None
    out: dict = {"blind": summary(blind, f"{LABELS[model]} blind", {})}
    items = items_for()
    rows = rows_of(blind)
    ids = list(rows)
    out["prior"] = blind_prior([rows[i]["pred_letter"] for i in ids], [items[i].candidates for i in ids], maj_value)
    if have(framed):
        pr = paired(framed, blind)
        pr["h1_falsified"] = pr["p_mcnemar"] < H1_ALPHA and pr["diff"] > 0
        out["framed_vs_blind"] = pr
    if have(vshuf):
        vitems = items_for(value_shuffle_seed=1)
        vrows = rows_of(vshuf)
        vids = list(vrows)
        out["value_shuffled"] = blind_prior([vrows[i]["pred_letter"] for i in vids],
                                            [vitems[i].candidates for i in vids], maj_value)
    return out


def _perm_set(model: str, majority_value: str | None = None) -> dict | None:
    runs = [perm_run_id(model, k) for k in range(6)]
    present = [k for k, r in enumerate(runs) if have(r)]
    if len(present) < 2:
        return None
    rows = {k: rows_of(runs[k]) for k in present}
    items = {k: items_for(permutation=k) for k in present}
    common = [i for i in rows[present[0]] if all(i in rows[k] for k in present)]
    correct, content, slots = [], [], []
    for i in common:
        c_row, t_row, s_row = [], [], []
        for k in present:
            r = rows[k][i]
            c_row.append(bool(r["correct"]))
            if r["pred_letter"] is None:
                t_row.append(None)
                s_row.append(None)
            else:
                j = LETTERS.index(r["pred_letter"])
                t_row.append(items[k][i].candidates[j])
                s_row.append(j)
        correct.append(c_row)
        content.append(t_row)
        slots.append(s_row)
    if majority_value is not None:
        base = items_for()
        vs_majority = paired_vs_baseline(correct, [base[i].answer == majority_value for i in common])
    else:
        vs_majority = None
    out = {"orderings": present, "complete": len(present) == 6, "n_items": len(common), "vs_majority_paired": vs_majority,
           "perm_avg": perm_averaged_accuracy(correct), **consistency(content, correct),
           "cramers_v": cramers_v_position(slots, 3)}
    rows_all = [r for k in present for r in rows[k].values()]
    out["cost"] = cost_per_correct(rows_all, PRICES)
    return out


def _joined_200(model: str) -> list[dict] | None:
    a, b = run_id(model, "n100"), run_id(model, "s100-n100")
    if not (have(a) and have(b)):
        return None
    return _rows_list(a) + _rows_list(b)


def phase2() -> dict:
    out: dict = {"hypotheses": {}}
    H = out["hypotheses"]

    print("\nF. MAJORITY-LABEL BASELINES")
    try:
        maj100, maj200 = _majority(100), _majority(200)
    except Exception as e:  # needs json/action_count.json (Hugging Face) on first use
        print(f"  (unavailable: {e})")
        return out
    out["majority"] = {"items_1_100": maj100, "items_1_200": maj200}
    for name, mj in (("items 1-100", maj100), ("items 1-200", maj200)):
        v, s = mj["value"], mj["slot"]
        print(f"  {name}: always answer {v['value']!r}: {v['k']}/{v['n']} = {v['acc']:.0%} [{v['lo']:.1%}, {v['hi']:.1%}]; "
              f"always pick slot {s['value']}: {s['k']}/{s['n']} = {s['acc']:.0%} [{s['lo']:.1%}, {s['hi']:.1%}]")
    maj_value = maj100["value"]["value"]

    print(f"\nG. BLIND PRIOR (no frames). H1 alpha = {H1_ALPHA:.4f} (Bonferroni over 3)")
    out["blind"] = {}
    for m in MODEL_IDS:
        b = _blind(m, maj_value)
        if b is None:
            print(f"  {LABELS[m]:11s} (missing {run_id(m, 'n100-blind')})")
            continue
        out["blind"][m] = b
        s, pr = b["blind"], b["prior"]
        line = (f"  {LABELS[m]:11s} blind {s['correct']}/{s['n']} = {s['acc']:.0%} [{s['lo']:.1%}, {s['hi']:.1%}]  "
                f"slot shares {[round(pr['slot_share'][L]['acc'], 2) for L in 'ABC']}  "
                f"picks {maj_value!r} {pr['value_share']['acc']:.0%}")
        if "framed_vs_blind" in b:
            f = b["framed_vs_blind"]
            line += (f"  framed-blind {f['diff']:+.1%} b={f['b_discordant']} c={f['c_discordant']} p={f['p_mcnemar']:.4f}"
                     f"{' H1 FALSIFIED' if f['h1_falsified'] else ''}")
        print(line)
        if "value_shuffled" in b:
            vs = b["value_shuffled"]
            sep = vs["separated"]
            print(f"  {'':11s} value-shuffled: middle share {vs['middle_share']['acc']:.0%} "
                  f"[{vs['middle_share']['lo']:.1%}, {vs['middle_share']['hi']:.1%}]; on {sep['items']} items where "
                  f"{maj_value!r} is off the middle: middle {sep['middle']} vs {maj_value!r} {sep['value']} "
                  f"(binomial p={sep['p_binomial'] if sep['p_binomial'] is None else round(sep['p_binomial'], 4)})")
    h1 = [b["framed_vs_blind"] for b in out["blind"].values() if "framed_vs_blind" in b]
    H["H1"] = ({"verdict": "falsified" if any(x["h1_falsified"] for x in h1) else "holds",
                "basis": "framed vs blind McNemar per model at alpha 0.0167; falsified if any model's framed run beats its blind run"}
               if len(h1) == 3 else {"verdict": "incomplete", "basis": f"{len(h1)} of 3 framed-vs-blind pairs"})
    hv = out["blind"].get("haiku45", {}).get("value_shuffled")
    if hv:
        mid, sep = hv["middle_share"]["acc"], hv["separated"]
        verdict = ("holds" if mid >= 0.5 else
                   "falsified" if sep["value"] > sep["middle"] else "neither: middle under 50% and picks do not follow the value")
        H["H2"] = {"verdict": verdict, "middle_share": mid, "separated": sep,
                   "basis": "Haiku blind, values shuffled off the middle: middle share >= 50% holds; picks following the value falsify"}
    else:
        H["H2"] = {"verdict": "incomplete", "basis": "no Haiku value-shuffled blind run"}

    print("\nH. PERMUTATION SETS (ordering 0 = the phase 1 run)")
    out["permutations"] = {}
    h3_parts = []
    lo, hi = maj100["value"]["lo"], maj100["value"]["hi"]
    for m in MODEL_IDS:
        ps = _perm_set(m, maj_value)
        if ps is None:
            print(f"  {LABELS[m]:11s} (fewer than 2 orderings present)")
            continue
        out["permutations"][m] = ps
        pa, cs, ca, cv = ps["perm_avg"], ps["consistency"], ps["circular_accuracy"], ps["cramers_v"]
        print(f"  {LABELS[m]:11s} orderings {ps['orderings']} on {ps['n_items']} items: perm-averaged {pa['acc']:.1%} "
              f"[{pa['lo']:.1%}, {pa['hi']:.1%}]; consistency {cs['k']}/{cs['n']} = {cs['acc']:.0%} [{cs['lo']:.1%}, {cs['hi']:.1%}]; "
              f"correct under all {ca['k']}/{ca['n']}; Cramer's V {cv['v']:.3f} (slots {cv['slot_counts']}, p={cv['p']:.3g})")
        vm = ps["vs_majority_paired"]
        if vm:
            print(f"  {'':11s} paired vs always {maj_value!r}: {vm['diff']:+.1%} [{vm['lo']:+.1%}, {vm['hi']:+.1%}] "
                  f"{'distinguishable' if vm['distinguishable'] else 'not distinguishable'}")
        if ps["complete"]:
            h3_parts.append({"model": m, "consistency": cs["acc"], "max": H3_CONSISTENCY_MAX[m],
                             "perm_avg": pa["acc"], "inside_majority_interval": lo <= pa["acc"] <= hi})
    if len(h3_parts) == 3:
        ok = all(p_["consistency"] < p_["max"] and p_["inside_majority_interval"] for p_ in h3_parts)
        H["H3"] = {"verdict": "holds" if ok else "falsified", "parts": h3_parts, "majority_interval": [lo, hi],
                   "basis": "consistency under 50% (Haiku) and 75% (Sonnet, Opus); every perm-averaged accuracy inside the majority-baseline Wilson interval",
                   # Not the registered criterion: the registered one compares a point estimate with the baseline's
                   # interval only. This paired item-bootstrap difference is the test of "beats the baseline".
                   "paired_vs_majority": {p_["model"]: out["permutations"][p_["model"]]["vs_majority_paired"] for p_ in h3_parts}}
    else:
        H["H3"] = {"verdict": "incomplete", "basis": f"{len(h3_parts)} of 3 complete permutation sets", "parts": h3_parts}

    print("\nI. 200 ITEMS (original 1-100 joined to 101-200)")
    hk, sn = _joined_200("haiku45"), _joined_200("sonnet55")
    if hk and sn:
        cmp = compare_runs(sn, hk)
        pr = cmp["paired"]
        mid = sum(1 for r in hk if r["pred_letter"] == "B")
        w = wilson(mid, len(hk))
        out["items_200"] = {"sonnet_vs_haiku": cmp, "haiku_middle_share": {"k": mid, "n": len(hk), "acc": w.acc, "lo": w.lo, "hi": w.hi}}
        print(f"  {cmp['summary']}")
        print(f"  Haiku middle share {mid}/{len(hk)} = {w.acc:.0%} [{w.lo:.1%}, {w.hi:.1%}]")
        H["H4"] = {"verdict": "holds" if pr["verdict"] == "tied" and w.acc > 0.5 else "falsified",
                   "basis": "Sonnet vs Haiku tied on 200 items and Haiku middle share above 50%"}
    else:
        print("  (missing items 101-200 runs)")
        H["H4"] = {"verdict": "incomplete", "basis": "items 101-200 runs missing"}

    print("\nJ. FRAMES (Haiku)")
    f4, f8, f16 = run_id("haiku45", "n100-f4"), run_id("haiku45", "n100"), run_id("haiku45", "n100-f16")
    out["frames"] = {}
    for a_, b_ in ((f4, f16), (f4, f8), (f8, f16)):
        if have(a_) and have(b_):
            r = paired(a_, b_)
            out["frames"][f"{a_} vs {b_}"] = r
            print(f"  {a_.rsplit('-', 1)[-1]:>5s} vs {b_.rsplit('-', 1)[-1]:<5s} diff {r['diff']:+.1%} "
                  f"b={r['b_discordant']} c={r['c_discordant']} p={r['p_mcnemar']:.3f} {r['verdict']}")
    key = f"{f4} vs {f16}"
    H["H5"] = ({"verdict": "holds" if abs(out["frames"][key]["diff"]) < H5_MAX_POINTS else "falsified",
                "diff": out["frames"][key]["diff"], "basis": "4 vs 16 frames moves Haiku by under 5 points"}
               if key in out["frames"] else {"verdict": "incomplete", "basis": "frame runs missing"})

    print("\nK. HARNESS PARITY (lmms-eval)")
    pf = RESULTS_DIR / "validation" / "parity_diff.json"
    if pf.exists():
        par = json.loads(pf.read_text())
        out["parity"] = par
        print(f"  agree on {par['agree']}/{par['n']} answers; lmms-eval unparsed {par.get('lmms_unparsed', 0)}")
        H["H6"] = {"verdict": "holds" if par["agree"] >= H6_MIN_AGREE * par["n"] else "falsified",
                   "basis": "lmms-eval and this pipeline agree on at least 90 of 100 Haiku answers"}
    else:
        print("  (no results/validation/parity_diff.json)")
        H["H6"] = {"verdict": "incomplete", "basis": "parity run not done"}

    print("\nL. OPUS REPEAT (ordering 0, cache off)")
    a_, b_ = run_id("opus55", "n100"), run_id("opus55", "n100-rep2")
    if have(a_) and have(b_):
        r = paired(a_, b_)
        out["opus_repeat"] = r
        print(f"  same letter {r['same_letter']}/{r['n']}; b={r['b_discordant']} c={r['c_discordant']} "
              f"diff {r['diff']:+.1%} p={r['p_mcnemar']:.3f} {r['verdict']}")
    else:
        print("  (missing)")

    print("\nM. COST PER CORRECT ANSWER (list price on every call's tokens)")
    out["cost"] = {}
    for f in sorted(RESULTS_DIR.glob("*-action_count-*.jsonl")):
        rid_ = f.stem
        c = cost_per_correct(_rows_list(rid_), PRICES)
        out["cost"][rid_] = c
        per = "n/a" if c["cost_per_correct"] is None else f"${c['cost_per_correct']:.4f}"
        print(f"  {rid_:42s} {c['correct']:3d}/{c['n']}  ${c['cost_per_100_items']:.3f} per 100 items  {per} per correct")
    for m, ps in out["permutations"].items():
        c = ps["cost"]
        per = "n/a" if c["cost_per_correct"] is None else f"${c['cost_per_correct']:.4f}"
        print(f"  {LABELS[m] + ' permutation set':42s} {c['correct']:3d}/{c['n']}  {per} per correct")

    print("\nHYPOTHESES")
    for h, v in H.items():
        print(f"  {h}: {v['verdict']}  ({v['basis']})")
    return out

if __name__ == "__main__":
    main()
