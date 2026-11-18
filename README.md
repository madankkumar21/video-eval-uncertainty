# video-eval-uncertainty

**Why this exists.** Contextual advertising places an ad beside content that matches a brief. At work I built contextual advertising packages on video content. Results often looked right and were wrong. A tagging agent dropped an exclusion that the brief required. Reruns returned different scenes. I only knew because I watched the clips. Someone asked how I knew the tags were right. I had a process to show and no number. This repo is the measurement I wanted, built on public data and public models.

**The question.** A video benchmark prints one accuracy number per model. How much of that number comes from the video, and how much from guessing well? And when two models land at 85% and 84%, is that a difference or noise?

**The method.** Run a public benchmark slice (MVBench `action_count`) against a public API model, one call per question, logging tokens and dollars. Grade each answer. Put a Wilson interval on accuracy. Compare two models with McNemar on the discordant items and a paired cluster-bootstrap difference, and report "better" or "tied". Wrap the same run in a durable workflow engine so a crash doesn't re-pay for finished questions and a person approves before results publish.

Open data, public models, no proprietary anything.

**Durable execution.** The Temporal engine is in `engines/temporal_app/`. The plain loop and Temporal face the same retry, crash and approval tests in [COMPARISON.md](COMPARISON.md).

## Layout

```
core/        plain Python, never imports an engine; every function is idempotent
  tasks.py   load items; fetch only the needed videos from Hugging Face by range request
  frames.py  uniform frame sampling with PyAV, cached on disk
  model.py   one model call; SQLite result cache; price table; retryable vs fatal errors; stub models
  score.py   letter-by-position grading
  stats.py   Wilson, McNemar, paired cluster bootstrap, verdict
  publish.py results/<run_id>.jsonl + summary
engines/
  plain.py       the baseline loop (loses in-flight progress on a crash)
  temporal_app/  workflow + activities + worker + client CLI
tests/           known-answer tests for the statistics
COMPARISON.md    the same scenarios run on each engine
```

## Run it

```bash
uv sync --extra temporal --group dev
uv run pytest
cp .env.example .env            # add the API key for real models; stub models need no key

# plain loop, stub model (no key, no cost)
uv run python -m engines.plain --model stub --n 10 --yes
uv run python -m engines.plain --model stub-b --n 10 --yes --compare-with stub

# real model: 3-item smoke test, then 100
uv run python -m engines.plain --model claude-haiku-4-5-20251001 --n 3
uv run python -m engines.plain --model claude-haiku-4-5-20251001 --n 100
```

### Temporal

```bash
brew install temporal
temporal server start-dev --db-filename results/temporal.db     # keep the db file or history dies with the server
uv run python -m engines.temporal_app.worker
uv run python -m engines.temporal_app.run start   --run-id demo --model stub --n 10
uv run python -m engines.temporal_app.run status  --run-id demo
uv run python -m engines.temporal_app.run approve --run-id demo --decision yes --wait
```

`scripts/temporal_scenarios.sh` replays scenarios 1 to 3 and prints the API-call counts.

## Knobs

| Env var | Effect |
|---|---|
| `VEU_ANTHROPIC_API_KEY` (or `ANTHROPIC_API_KEY`) | required for non-stub models. Use the `VEU_` name in a Claude Code cloud environment. |
| `VEU_CACHE=off` | bypass the SQLite result cache, so an engine's own resume is what you measure |
| `VEU_STUB_DELAY_S=1` | slow the stub down so there is time to kill a worker mid-run |
| `VEU_FAIL_ITEM=<item_id>` | the stub raises a retryable error once on that item |

## Costs

Measured: Haiku 4.5 at 8 frames of 768 px long edge is about 3,914 input tokens (3,900 to 5,026) and 9 output tokens per question, about $0.0040 each. The 100-question run is about 40 cents. Answers come back as structured output (`{"answer": "B"}`), which removed the parse failures seen with a plain-text reply. The price table is in `core/model.py`; pin dated model ids in results.

## Status

- Done: core, plain loop, Temporal with scenarios 1 to 3 measured with verified kills (COMPARISON.md).
- Done: three models on the same 100 items, all pairwise tied (Opus 52, Sonnet 48, Haiku 44); shuffled, repeated, re-labelled and default-temperature reruns show Haiku 4.5 anchors on the middle option and the other two follow content (RESULTS.md).
- Done: phase 2, pre-registered (`docs/PHASE2_PLAN.md`): blind runs, all six option orderings, 200 items and frame counts. Without video, all three models score near "always answer 3" (41%); only Opus beats that baseline once option order is averaged out (RESULTS.md).
- Done: H7, the human count. From the same 8 frames a person scored 8 of 20, the same as "always 3" and the models on those items; with the full clip, 20 of 20. The 8-frame input cannot support the task; the labels hold (RESULTS.md).
- Done: the buyer post, published in this repo as `docs/posts/buyer-post.md`. It goes from a work use case to the benchmark to five questions a buyer should ask. The first question is whether a person can answer from the model's exact input.
- Not run: H6, lmms-eval parity on the same 100 videos. A 1-item smoke test found a scoring problem (`results/validation/h6_not_run.md`).
- Next: scenarios 4 and 5 (workflow versioning, large batches), `mcp/server.py` exposing `compare(model_a, model_b)`.

## Data and licences

- **Code.** The code in this repo uses the MIT License. See [LICENSE](LICENSE).
- **Benchmark.** The benchmark is MVBench from OpenGVLab. The code fetches the items and videos it needs from Hugging Face ([`OpenGVLab/MVBench`](https://huggingface.co/datasets/OpenGVLab/MVBench)) at run time.
- **MVBench licence.** The MVBench dataset card gives the licence as MIT. The card also says that video copyrights stay with the original video creators or platforms. It limits the videos to academic research use. It says that the data can be subject to other agreements.
- **No videos here.** This repo does not redistribute the MVBench videos. `results/` holds item IDs, model answers and one MVBench question with its options (`results/validation/lmms_smoke_samples_mvbench_action_count.jsonl`).
- **Patch.** `patches/` holds a patch against lmms-eval 0.7.3. The patch changes only `lmms_eval/models/simple/claude.py`. The lmms-eval LICENSE puts the code in `lmms_eval/models` under the Apache License 2.0, so the patch is under that licence. See the [lmms-eval LICENSE](https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/main/LICENSE).
