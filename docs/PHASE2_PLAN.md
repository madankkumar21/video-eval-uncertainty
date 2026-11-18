# Phase 2 plan: pre-registration (approved 2026-10-04)

*Note on the public copy: I removed personal scheduling notes and references to private working notes. The hypotheses, tests and thresholds are unchanged from the pre-registered text.*

## Context
Phase 1 showed three frontier models tied on 100 MVBench `action_count` items and one of them (Haiku 4.5) anchored on the middle option. I want phase 2 to be useful to the eval community and to buyers, and to show depth in multimodal evaluation. Decisions: under $30 more API spend (so far $6.26); audience both, buyer first; runs first (by about 10/15), writing after.

**What the research pass established.** The literature's standard for option-position bias is to estimate a content-free prior and report permutation-averaged accuracy plus a consistency rate (PriDe, MMBench CircularEval, SCOPE null prompts, BOLD ablations, Tamba's `inspect_permute`, "cross-ordering flip rate"). No published work reports a middle-option preference or shuffles MVBench options, so our finding is new as stated. lmms-eval has no shuffle flag and no interval in MVBench output, but `metrics.py` already holds unwired `clustered_stderr`, `paired_ttest` and `power_analysis`: a real, small gap for a pull request. Inspect already ships `shuffle_choices` and `ci_wilson`. TVBench reports that `action_count`'s correct answer is "3" on 90 of 200 items; our own count on the first 100 in file order was 41, so the majority-label baseline needs computing on exactly our slice. If "always answer 3" scores near the models, that is the headline a buyer needs. NIST AI 800-2 asks for intervals on every statistic and cost reported next to performance.

## The six questions phase 2 answers
1. **Label prior.** With no frames at all, what does each model score and pick? Is Haiku's prior positional (middle slot) or a value prior ("3")? A values-shuffled blind variant separates the two.
2. **Debiased accuracy.** Over all 6 orderings of 3 options, what is each model's permutation-averaged accuracy, its consistency (same content under every order), and Cramér's V for position dependence?
3. **Majority baseline.** What does "always answer the most common label" score on our slice, with an interval, next to the models?
4. **Does the slice size matter?** Full 200 items for Haiku and Sonnet: do the tie and the anchoring hold?
5. **Frames.** 4 vs 8 vs 16 frames for Haiku: does more evidence shrink the prior?
6. **Harness parity.** One Haiku run through lmms-eval's own `mvbench_action_count`: same answers as our pipeline?

## Pre-registered hypotheses (commit the hash before the first paid run)
- H1: each model's framed accuracy is not distinguishable from its blind accuracy on action_count (McNemar, Bonferroni over 3). Falsified if any model beats its own blind run at alpha 0.0167.
- H2: Haiku's blind picks stay ≥50% on the middle slot when option values are shuffled (positional prior). Falsified if its picks follow the value "3" instead.
- H3: permutation consistency is under 50% for Haiku and under 75% for Sonnet and Opus; permutation-averaged accuracy for all three lies inside the majority-baseline Wilson interval.
- H4: on 200 items, Sonnet vs Haiku stays tied and Haiku's middle share stays above 50%.
- H5: 4 vs 16 frames moves Haiku by under 5 points.
- H6: lmms-eval and our pipeline agree on at least 90 of 100 Haiku answers.

## Addition, pre-registered 2026-10-06: H7, the human count
Added after H1 to H6 were analysed. Phase 2 found that taking the frames away cost each model 5 to 13 points, none significant. The rival explanation is that 8 sampled frames cannot support counting at all. H7 tests that with no API spend.

- H7: a person counts the action correctly from the same 8 frames the models saw on at least 15 of 20 items. Falsified at 14 or fewer. One flipped item changes the verdict at the boundary, and the script reports that.
- Items: 20 of the first 100, seeded (7), stratified by the true answer value so the sample is not all "3". Selection is in `scripts/human_count.py`; the sheet is blind (frames, question, options in original order, no answers).
- Second pass: misses only, with the full clip. A miss the full video fixes is frame sampling. A miss it does not fix is the task or its label.
- Reported alongside: Wilson interval on k/20, each model's correct count on the same 20 items, accuracy by sure/unsure, wrong answers among items flagged impossible.
- Labeling basis: the MVBench `answer` field, as everywhere in the repo. My count is the measurement, not a second label.
- What it decides: H7 holds, the "most of the score does not come from the video" headline stands. H7 falsified and the full video fixes the misses, the headline becomes "8-frame sampling cannot support this task". H7 falsified and the full video does not fix them, the labels are checked before publishing.
- Commands: `scripts/human_count.py`. Worst case: one hour of labeling.

## Runs and cost (list prices; Haiku $0.004, Sonnet $0.008, Opus $0.017 per 8-frame item)
| Run | Items × calls | Cost |
|---|---|---|
| Blind baseline, 3 models, as-is and values-shuffled | 100 × 2 × 3, text only | about $0.10 |
| 6 orderings on action_count, first 100 (1 ordering exists) | 500 new calls × 3 models | Haiku $2.0, Sonnet $4.0, Opus $8.5 |
| Items 101–200, original order, Haiku and Sonnet | 100 × 2 | $1.2 |
| Frames 4 and 16, Haiku, first 100 | 200 | $1.0 |
| lmms-eval parity, Haiku, 100 items | 100 | $0.4 |
| Opus repeat of one ordering (sampling variance) | 100 | $1.7 |
| **Total** | | **about $19**, under the $30 cap |

Optional, $0: Qwen2.5-VL 7B locally via MLX (overnight) as the open-weight comparison. Batch API would halve the above but needs new code; not in this phase.

## Engineering (zero API cost)
- `core/tasks.py`: `permutation: int | None` (0–5, deterministic per item) alongside `shuffle_seed`; `blind: bool` and `value_shuffle_seed` in `core/model.py` (no frames; same structured output).
- `scripts/handoff_analysis.py`: majority-label baseline with Wilson interval; permutation-averaged accuracy; consistency; Cramér's V; per-position prior from the blind runs; cost-per-correct-answer; keep single-flip fragility and Bonferroni.
- `docs/index.html` (GitHub Pages): per model, raw accuracy, blind accuracy, debiased accuracy, consistency, Cramér's V, intervals, cost per 100 items, and a cost-vs-debiased-accuracy chart (NIST 3.2); an inline sample-size calculator using the observed disagreement rates.
- lmms-eval: install 0.7.3, run `mvbench_action_count` with its Claude wrapper on Haiku, diff answers item by item.
- Upstream PR to lmms-eval, scoped small: Wilson interval and stderr in MVBench output, and a seeded option-shuffle switch, citing the results page as motivation. Open the First Issue before the PR per their contributor funnel.

## Artifacts, in order
1. **Buyer post (under 1,200 words):** "How to read a multimodal leaderboard before you buy." The three questions from the video, plus the majority baseline and the blind baseline as the two numbers to demand.
2. **Results page** on the repo, then make the repo public.
3. **lmms-eval issue and PR.**
4. **Evaluator post (under 1,500 words):** what `action_count` measures for frontier models: label prior vs video. Cross-link Inspect's `shuffle_choices` and `ci_wilson` so Inspect users see it applies to them.

## Timeline
- Before 10/15: engineering; the runs in the table above; analysis script output committed.
- After 10/20: posts, results page, PR.

## Not changed
Phase 1 numbers stand. No Video-MME clustered study this phase (254 hours of video to fetch; a 150-video pilot is a phase 3 candidate). No thinking-on conditions.

## Verification
- Every hypothesis has a number it is falsified by, written before the run.
- Every figure on the results page is produced by a script from `results/*.jsonl`, with the commit hash shown.
- Costs recorded per run from the `calls` table and compared with the table above.
- Harness parity: item-level diff file committed.
