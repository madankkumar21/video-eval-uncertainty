"""Known-answer tests for core.bias."""

import math

from core.bias import (blind_prior, consistency, cost_per_correct, cramers_v_position, majority_baseline,
                       perm_averaged_accuracy)


def test_majority_baseline():
    m = majority_baseline(["3"] * 41 + ["2"] * 30 + ["4"] * 29)
    assert m["value"] == "3" and m["k"] == 41 and m["n"] == 100
    assert abs(m["lo"] - 0.3187) < 1e-3 and abs(m["hi"] - 0.5080) < 1e-3  # Wilson 41/100, by formula


def test_perm_averaged_accuracy():
    # item 0 always right, item 1 right on half the orderings, item 2 never
    correct = [[True] * 6, [True, False] * 3, [False] * 6]
    r = perm_averaged_accuracy(correct)
    assert math.isclose(r["acc"], 0.5)
    assert r["per_ordering"] == [2 / 3, 1 / 3] * 3
    assert r["lo"] <= 0.5 <= r["hi"] and r["n_items"] == 3 and r["n_orderings"] == 6


def test_consistency_and_circular():
    content = [["3"] * 6, ["3", "2", "3", "3", "3", "3"], ["4", None, "4", "4", "4", "4"]]
    correct = [[True] * 6, [True, False, True, True, True, True], [False] * 6]
    r = consistency(content, correct)
    assert r["consistency"]["k"] == 1 and r["consistency"]["n"] == 3
    assert r["circular_accuracy"]["k"] == 1


def test_cramers_v_extremes():
    always_b = [[1] * 6 for _ in range(50)]
    assert math.isclose(cramers_v_position(always_b, 3)["v"], 1.0)
    uniform = [[0, 1, 2, 0, 1, 2] for _ in range(50)]
    r = cramers_v_position(uniform, 3)
    assert math.isclose(r["v"], 0.0, abs_tol=1e-12) and math.isclose(r["p"], 1.0)
    partial = [[1, 1, 1, 0, 2, 1] for _ in range(50)]  # middle 4 of 6
    assert 0.0 < cramers_v_position(partial, 3)["v"] < 1.0


def test_blind_prior_separates_middle_from_value():
    # value "3" is never in the middle; the model picks the middle 7 times and "3" twice
    cands = [("3", "2", "4")] * 10
    picks = ["B"] * 7 + ["A"] * 2 + [None]
    r = blind_prior(picks, cands, value="3")
    assert r["slot_share"]["B"]["k"] == 7 and r["parse_failures"] == 1
    assert r["value_share"]["k"] == 2
    assert r["separated"] == {"items": 10, "middle": 7, "value": 2, "p_binomial": r["separated"]["p_binomial"]}
    assert 0.1 < r["separated"]["p_binomial"] < 0.2  # binomial(7 of 9) two-sided = 0.18


def test_cost_per_correct_uses_list_price_not_billed():
    rows = [{"model_id": "m", "input_tokens": 1_000_000, "output_tokens": 0, "cost_usd": 0.0, "correct": True},
            {"model_id": "m", "input_tokens": 1_000_000, "output_tokens": 100_000, "cost_usd": 1.5, "correct": False}]
    r = cost_per_correct(rows, {"m": (1.0, 5.0)})
    assert r["cost_uncached"] == 2.5 and r["cost_billed"] == 1.5
    assert r["cost_per_correct"] == 2.5 and r["cost_per_100_items"] == 125.0


def test_paired_vs_baseline():
    from core.bias import paired_vs_baseline
    # model right on 60 of 100 items under every ordering; baseline right on 40 of them
    correct = [[True] * 6] * 60 + [[False] * 6] * 40
    base = [True] * 40 + [False] * 60
    r = paired_vs_baseline(correct, base)
    assert abs(r["diff"] - 0.20) < 1e-12 and r["distinguishable"] and r["lo"] > 0
    same = paired_vs_baseline([[True] * 6] * 40 + [[False] * 6] * 60, base)
    assert same["diff"] == 0.0 and not same["distinguishable"]
