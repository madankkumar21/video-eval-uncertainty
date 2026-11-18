"""Phase 2 plumbing: the run table, the spend gate and the parity diff."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import parity_diff  # noqa: E402
import phase2_spend  # noqa: E402
from phase2_runs import BUDGET_CAP_USD, PHASE2_RUNS, total_estimate  # noqa: E402


def test_run_table_is_unique_and_under_cap():
    ids = [r["run_id"] for r in PHASE2_RUNS]
    assert len(ids) == len(set(ids))
    assert total_estimate() < BUDGET_CAP_USD


def _summary(d: Path, run_id: str, cost: float) -> None:
    (d / f"{run_id}.summary.json").write_text(json.dumps({"cost_usd": cost}))


def test_spend_gate(tmp_path):
    first = PHASE2_RUNS[0]
    code, lines = phase2_spend.gate(first["run_id"], results_dir=tmp_path)
    assert code == 0 and lines[-1] == "GO"
    _summary(tmp_path, first["run_id"], first["estimate"] * 1.6)  # overrun
    code, lines = phase2_spend.gate(PHASE2_RUNS[1]["run_id"], results_dir=tmp_path)
    assert code == 2 and any("more than 1.5x" in x for x in lines)
    code, lines = phase2_spend.gate(PHASE2_RUNS[1]["run_id"], parity=BUDGET_CAP_USD, results_dir=tmp_path / "x")
    assert code == 2 and any("past the cap" in x for x in lines)
    code, _ = phase2_spend.gate("not-a-run", results_dir=tmp_path / "x")
    assert code == 2
    code, lines = phase2_spend.gate("lmms-parity", results_dir=tmp_path / "x")
    assert code == 0 and any("lmms-eval parity" in x for x in lines)
    (tmp_path / "v" / "validation").mkdir(parents=True)
    (tmp_path / "v" / "validation" / "parity_diff.json").write_text(json.dumps({"cost_usd": 5.0}))
    code, lines = phase2_spend.gate(None, results_dir=tmp_path / "v")  # parity read from file, and overrun
    assert code == 2 and any("parity cost $5.000" in x for x in lines)


def test_strict_letter():
    assert parity_diff.strict_letter("B") == "B"
    assert parity_diff.strict_letter("(C) 4") == "C"
    assert parity_diff.strict_letter("A. 3") == "A"
    assert parity_diff.strict_letter("Looking at the sequence of images, I can see a person's hand") is None
    assert parity_diff.lmms_letter("Looking at the sequence of images, I can see a person's hand") == "A"  # lmms-eval's reading


def test_parity_diff_doc_id_and_truncation(tmp_path, monkeypatch):
    ours = [{"item_id": f"action_count:video_{i}", "pred_letter": "A"} for i in range(3)]
    monkeypatch.setattr(parity_diff, "load_run", lambda run: ours)
    log = tmp_path / "s.jsonl"
    log.write_text("\n".join(json.dumps(x) for x in [
        {"doc_id": 0, "filtered_resps": "Looking at the sequence of images, I can see a person's hand appearing in",
         "token_counts": [{"input_tokens": 9642, "output_tokens": 16}]},
        {"doc_id": 1, "filtered_resps": "(A)", "token_counts": [{"input_tokens": 9000, "output_tokens": 3}]},
        {"doc_id": 2, "filtered_resps": "B", "token_counts": [{"input_tokens": 9000, "output_tokens": 1}]},
    ]))
    out = parity_diff.diff(log, "r", item_ids=[f"action_count:video_{i}" for i in range(3)])
    assert out["n"] == 3 and out["truncated"] == 1 and out["unparsed"] == 1
    assert out["agree"] == 1  # item 1; item 0 is truncated (lmms-eval would score its "a" as A), item 2 disagrees
    assert out["lmms_reads_free_text_as_letter"] == 1


def test_lmms_letter_extraction():
    assert parity_diff.lmms_letter("B") == "B"
    assert parity_diff.lmms_letter("(C) 4") == "C"
    assert parity_diff.lmms_letter("A. 3") == "A"
    assert parity_diff.lmms_letter("The answer is b.") == "B"
    assert parity_diff.lmms_letter("three") is None


def test_parity_diff_on_a_synthetic_log(tmp_path, monkeypatch):
    ours = [{"item_id": f"action_count:video_{i}", "pred_letter": "B" if i % 4 else "A"} for i in range(8)]
    monkeypatch.setattr(parity_diff, "load_run", lambda run: ours)
    log = tmp_path / "s.jsonl"
    lines = []
    for i in range(8):
        text = "(B)" if i != 3 else "(C)"   # lmms says B everywhere except item 3; ours says A on items 0 and 4
        lines.append(json.dumps({"doc_id": i, "doc": {"video": f"video_{i}.mp4"}, "filtered_resps": [text],
                                 "token_counts": [{"input_tokens": 1000, "output_tokens": 5}]}))
    lines.append(json.dumps({"doc_id": 99, "doc": {"video": "other.mp4"}, "filtered_resps": ["A"]}))
    log.write_text("\n".join(lines))
    out = parity_diff.diff(log, "r")
    assert out["n"] == 8 and out["not_in_run"] == 1 and out["truncated"] == 0
    assert out["input_tokens"] == 8000 and out["output_tokens"] == 40
    assert out["cost_usd"] == round((8000 * 1.0 + 40 * 5.0) / 1e6, 4)  # Haiku 4.5 list price
    assert out["agree"] == 5  # items 1, 2, 5, 6, 7
    assert {d["item_id"] for d in out["disagreements"]} == {"action_count:video_0", "action_count:video_3", "action_count:video_4"}


def test_lmms_patch_touches_only_the_claude_wrapper():
    patch = (ROOT / "patches" / "lmms-eval-0.7.3-claude.patch").read_text()
    files = re.findall(r"^\+\+\+ b/(\S+)", patch, flags=re.M)
    assert files == ["lmms_eval/models/simple/claude.py"]
    added = [x for x in patch.splitlines() if x.startswith("+") and not x.startswith("+++")]
    assert not any("top_p=" in x for x in added)
    assert any("import av" in x for x in added)
