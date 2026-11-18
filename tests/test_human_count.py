"""H7: the 20-item human count sheet and its scoring."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import human_count as hc  # noqa: E402

VALUES = json.loads((ROOT / "results" / "validation" / "item_values.json").read_text())
JPEG_STUB = b"\xff\xd8\xff\xd9"  # smallest thing that is still a JPEG header and trailer


def _fake_data(tmp_path: Path, chosen: list[str]) -> Path:
    data = tmp_path / "data"
    rows = []
    for i in chosen:
        task, stem = i.split(":", 1)
        d = data / "frames" / task / stem / hc.FRAME_KEY
        d.mkdir(parents=True)
        for k in range(8):
            (d / f"{k:02d}.jpg").write_bytes(JPEG_STUB)
        rows.append({"video": f"{stem}.mp4", "question": f"How many times for {stem}?",
                     "candidates": VALUES[i]["candidates"], "answer": VALUES[i]["answer"]})
    (data / "json").mkdir()
    (data / "json" / "action_count.json").write_text(json.dumps(rows))
    return data


def test_selection_is_deterministic_stratified_and_from_the_first_100():
    chosen = hc.select_items(VALUES)
    assert chosen == hc.select_items(VALUES)
    assert len(chosen) == hc.N_ITEMS == len(set(chosen))
    first100 = set(list(VALUES)[:100])
    assert set(chosen) <= first100
    # proportional to the answer mix of the first 100: "3" is 41 of 100, so 8 of 20
    mix = {}
    for i in chosen:
        mix[VALUES[i]["answer"]] = mix.get(VALUES[i]["answer"], 0) + 1
    assert mix["3"] == 8
    assert len(mix) >= 4
    assert hc.select_items(VALUES, seed=8) != chosen


def test_sheet_shows_frames_and_options_but_no_answers(tmp_path):
    chosen = hc.select_items(VALUES)
    data = _fake_data(tmp_path, chosen)
    sheet, answers = hc.write_sheet(chosen, VALUES, data_dir=data, out_dir=tmp_path / "out")
    txt = sheet.read_text()
    assert txt.count("<img ") == 8 * hc.N_ITEMS
    for i in chosen:
        assert i in txt
        for L, c in zip(hc.LETTERS, VALUES[i]["candidates"]):
            assert f"({L}) {c}" in txt
    # no item's truth letter appears anywhere as a marked answer
    assert "correct" not in txt.lower()
    assert "truth" not in txt.lower()
    rows = list(csv.DictReader(open(answers)))
    assert [r["item_id"] for r in rows] == chosen
    assert all(r["letter"] == "" for r in rows)
    assert "answer" not in "".join(rows[0].keys())


def test_sheet_fails_loudly_when_frames_are_missing(tmp_path):
    chosen = hc.select_items(VALUES)
    data = _fake_data(tmp_path, chosen)
    victim = hc.frames_dir(chosen[3], data) / "07.jpg"
    victim.unlink()
    try:
        hc.write_sheet(chosen, VALUES, data_dir=data, out_dir=tmp_path / "out")
    except FileNotFoundError as e:
        assert chosen[3] in str(e)
    else:
        raise AssertionError("missing frame did not fail")


def _truth(i: str) -> str:
    return hc.LETTERS[VALUES[i]["candidates"].index(VALUES[i]["answer"])]


def _write_answers(path: Path, chosen: list[str], n_right: int, full_video: dict[str, str] | None = None):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n", "item_id", "letter", "confidence", "impossible_from_frames", "seconds", "letter_full_video", "note"])
        for k, i in enumerate(chosen, 1):
            t = _truth(i)
            letter = t if k <= n_right else hc.LETTERS[(hc.LETTERS.index(t) + 1) % 3]
            conf = "sure" if k % 2 else "unsure"
            imp = "yes" if k > n_right and k % 2 == 0 else "no"
            w.writerow([k, i, letter, conf, imp, "", (full_video or {}).get(i, ""), ""])


def test_score_verdict_one_flip_and_splits(tmp_path):
    chosen = hc.select_items(VALUES)
    p = tmp_path / "human_count.csv"
    _write_answers(p, chosen, 15)
    out = hc.score(VALUES, p, results_dir=tmp_path)
    assert (out["correct"], out["n"], out["h7"]) == (15, 20, "holds")
    assert out["one_flip_changes_verdict"] is True
    assert out["sure"]["n"] + out["unsure"]["n"] == 20
    assert out["sure"]["correct"] + out["unsure"]["correct"] == 15
    assert out["impossible_flagged"] == out["impossible_and_wrong"] == 3
    assert 0.5 < out["lo"] < 0.75 < out["hi"] < 0.92
    assert out["full_video"] is None
    assert out["models_on_these_items"] == {}
    assert out["answer_mix"]["3"] == 8

    _write_answers(p, chosen, 14)
    out = hc.score(VALUES, p, results_dir=tmp_path)
    assert out["h7"] == "falsified" and out["one_flip_changes_verdict"] is True

    _write_answers(p, chosen, 18)
    out = hc.score(VALUES, p, results_dir=tmp_path)
    assert out["h7"] == "holds" and out["one_flip_changes_verdict"] is False


def test_score_full_video_recount_and_models_on_same_items(tmp_path):
    chosen = hc.select_items(VALUES)
    misses = chosen[12:20]
    fv = {misses[0]: _truth(misses[0]), misses[1]: _truth(misses[1]), misses[2]: "X"}
    p = tmp_path / "human_count.csv"
    _write_answers(p, chosen, 12, fv)
    run = tmp_path / "haiku45-action_count-n100.jsonl"
    with open(run, "w") as f:
        for k, i in enumerate(chosen):
            f.write(json.dumps({"item_id": i, "correct": k < 7}) + "\n")
    out = hc.score(VALUES, p, results_dir=tmp_path)
    assert out["full_video"] == {"rechecked": 3, "correct": 2, "misses_rechecked": 3, "misses_fixed_by_full_video": 2}
    assert out["models_on_these_items"] == {"haiku45": 7}


def test_score_refuses_a_half_filled_sheet(tmp_path):
    chosen = hc.select_items(VALUES)
    p = tmp_path / "human_count.csv"
    _write_answers(p, chosen, 20)
    rows = p.read_text().splitlines()
    rows[1] = rows[1].replace(f",{_truth(chosen[0])},", ",,", 1)
    p.write_text("\n".join(rows) + "\n")
    try:
        hc.score(VALUES, p, results_dir=tmp_path)
    except ValueError as e:
        assert "1 items" in str(e)
    else:
        raise AssertionError("half-filled sheet was scored")
