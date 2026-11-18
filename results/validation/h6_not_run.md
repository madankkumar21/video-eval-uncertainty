# H6 (lmms-eval parity): not run, 2026-10-05

I chose to skip the 100-item parity run after the 1-item smoke test. What the smoke test showed:

- **SDK pin.** `uv pip install anthropic` pulled 1.11.0, whose `messages.create` no longer accepts `temperature`. The wrapper failed client-side before any request. Fixed by pinning `anthropic<1.0` (0.125.0) in the parity venv only; the two-fix patch was unchanged.
- **16-token cap.** lmms-eval's MVBench template sets `max_new_tokens: 16`. Haiku 4.5 began describing the frames and was cut off before giving a letter: "Looking at the sequence of images, I can see a person's hand appearing in".
- **Scored correct anyway.** `mcq_acc` extracted "A" from the article "a" and the item scored 1 (ground truth A). `scripts/parity_diff.py`'s port of that parser does the same, so `lmms_unparsed = 0` does not catch it.
- **Samples have no `doc`.** 0.7.3 writes `doc_id`, `doc_hash`, `input`, `filtered_resps`, `token_counts`; `parity_diff.py` reads `s['doc']['video']` and raises KeyError. `doc_id` is the item's position in file order.
- **Token cost.** 9,642 input tokens for the item against about 3,914 in our pipeline: about $0.97 per 100 items against the $0.40 estimate.

Evidence: `lmms_smoke_samples_mvbench_action_count.jsonl`, `lmms_smoke.log`. Cost of the smoke test: about $0.01.
