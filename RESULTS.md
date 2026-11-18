# Results

Runs are reproducible from the commands in the README. Rows and summaries for every real run are tracked under `results/`; every figure below is computed by `scripts/handoff_analysis.py`, `scripts/position_bias.py` or `scripts/numbered_confound.py` from those rows.

## MVBench action_count, first 100 items, 8 frames at 768 px (2026-10-03)

| Model | Accuracy | Wilson 95% | Parse failures | Tokens in / out | Cost | p50 latency |
|---|---|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | 44/100 = 44.0% | [34.7%, 53.8%] | 0 | 391,357 / 900 | $0.384 | 1.18 s |
| `claude-sonnet-5-5` (between_tools) | 48/100 = 48.0% | [38.5%, 57.7%] | 0 | 399,704 / 1,000 | $0.793 | 1.88 s |

Chance on three options is 33.3%. The interval excludes chance, but only just: ten points of width on each side from 100 items.

Costs are what was billed. The Haiku run served 3 items from the result cache (97 paid calls) and the Sonnet run served 2 (98 paid calls); a full uncached run costs about $0.396 on Haiku, $0.809 on Sonnet and $1.76 on Opus at medium effort.

**Position bias, first run.** The correct answer is spread evenly across the three positions (A 35, B 35, C 30). The model's picks are not: it chose B 59 times, A 24, C 17. Accuracy by correct position: A 23%, B 74%, C 33%.

## Same items, options shuffled (seed 1), Haiku 4.5, 2026-10-03

Each item's options were permuted with a per-item seeded RNG (84 of 100 orders changed). Same model, same frames, same prompt. The 16 items whose order did not change have identical prompts, so they came from the result cache; the shuffled run made 84 real calls.

| Run | Accuracy | Wilson 95% | Picks A/B/C | Correct positions A/B/C | Cost |
|---|---|---|---|---|---|
| unshuffled | 44.0% | [34.7%, 53.8%] | 24 / 59 / 17 | 35 / 35 / 30 | $0.384 |
| shuffled | 39.0% | [30.0%, 48.8%] | 25 / 59 / 16 | 28 / 37 / 35 | $0.333 (84 paid calls) |

- **The pick distribution did not move.** B 59 times in both runs, after the options under the letters changed on 84 items. The marginal count alone does not show what drove each pick; the item-level split below does.
- **Split on the 62 items where the first-run choice changed position:** on 28 the model followed the answer text to its new letter; on 28 it stayed on the same letter with different content; on 6 it picked a third option. When the chosen option moved, the model followed the letter as often as the content.
- **Following the text is consistency, not counting ability.** Of the 28 items where the model followed the text, 17 were the same wrong count both times. Of the 28 items where it stayed on the letter, 22 were B.
- **Accuracy by correct position, shuffled run:** A 8/28, B 26/37, C 5/35. When the right answer sits at B the model gets about 70%; at A or C, 14 to 29%.
- **Paired comparison of the two runs:** difference +5.0 points, bootstrap [-6.0, +16.0], discordant 18 vs 13, McNemar p = 0.47: tied. The headline number barely moved, which is what you'd expect if the model is anchored on B and B is correct about a third of the time either way.

**What this means for the benchmark.** A reported 44% on this slice overstates counting ability. When the options move, the model follows the position as often as the content, and most position-following picks are the middle option. Any leaderboard number on a three-option task with a fixed option order carries this confound, and it is invisible without a shuffled rerun.

## Same items, options labelled 1/2/3 instead of A/B/C, Haiku 4.5, 2026-10-03

Same 100 items in the original order. Only the labels changed. The structured output enum became `["1","2","3"]`; results are stored as letters by position.

| Labels | Accuracy | Wilson 95% | Picks pos 1/2/3 | Correct positions 1/2/3 | Cost |
|---|---|---|---|---|---|
| A / B / C | 44.0% | [34.7%, 53.8%] | 24 / 59 / 17 | 35 / 35 / 30 | $0.384 |
| 1 / 2 / 3 | 35.0% | [26.4%, 44.7%] | 24 / 74 / 2 | 35 / 35 / 30 | $0.396 |

- **The anchoring got worse, not better.** With numbers, the middle option was chosen 74 times and the third option twice. Accuracy fell to 35%, and the interval now includes chance (33.3%).
- **Paired comparison, letters vs numbers:** +9.0 points for letters, bootstrap [+2.0, +16.0], discordant 11 vs 2, McNemar p = 0.022. Letters beat numbers for this model on this task at the conventional threshold, but the verdict is fragile: one item moving from 11 vs 2 to 10 vs 3 gives p = 0.092 (tied), and it does not survive a Bonferroni correction across the ten paired tests in this file (alpha 0.005). What it does survive is test-retest noise: a second temperature-0 run of the lettered prompt reproduced all 100 answers exactly, so the 13 discordant items are not sampling noise. Read it as a real but small effect that 100 items cannot nail down.
- **A confound to rule out.** On a counting task the options are themselves numbers, so a numeric label could be mistaken for a count. Checked: the returned label matched the true count on 8 of 100 items and matched any option text on 37 of 100, below what picking a number at random would give (the digit 2 is an option on 52 items). When the true count was 3, the model returned "2" on 36 of 41 items and "3" once. It is choosing the middle slot, not the number.
- **So the bias is not about the letter B.** It is a preference for the middle of three options that survives a change of label and a reshuffle of content. Numeric labels on numeric answers are still a bad idea; this run says so with a 9-point penalty.

## Second model: Sonnet 5.5 vs Haiku 4.5, same 100 items, 2026-10-03

Sonnet 5.5 ran with thinking at its lowest setting (`between_tools`, no extended thinking before the answer) so both models answer from the frames alone. Letters A/B/C, original order.

| Model | Accuracy | Wilson 95% | Picks A/B/C | Acc by correct position A/B/C | Cost |
|---|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | 44.0% | [34.7%, 53.8%] | 24 / 59 / 17 | 23% / 74% / 33% | $0.384 |
| `claude-sonnet-5-5` | 48.0% | [38.5%, 57.7%] | 39 / 31 / 30 | 51% / 40% / 53% | $0.793 |

**Paired comparison.** Sonnet +4.0 points, bootstrap [-9.0, +17.0], discordant 23 vs 19, McNemar p = 0.64. **Tied.** A four-point gap on 100 items is noise; with 42 discordant items it would take a 28 vs 14 split (McNemar p = 0.044, and the bootstrap interval then just excludes zero) to call it; 27 vs 15 is still tied.

**The position bias is Haiku's, not the task's, and not an artifact of temperature 0.** Three checks, pre-registered before the runs:

- *H3a, is it temperature?* Haiku at API-default sampling still anchors: picks 27 / 55 / 18 against 35 / 35 / 30 (goodness-of-fit p = 0.0001), accuracy 38% [29.1%, 47.8%], paired against the temperature-0 run: tied (9 vs 3, p = 0.15). Greedy decoding is not the cause.
- *H3b, does Sonnet follow content?* Sonnet shuffled (seed 1, 84 orders changed): 46% [36.6%, 55.7%], picks 33 / 35 / 32. Of the 64 items whose first-run choice moved, Sonnet followed the answer text on 56, stayed on the letter on 4, and picked a third option on 4. Haiku's split was 28 / 28 / 6. Sonnet follows content.
- *H3c, is Sonnet's even spread just sampling noise?* A second Sonnet run with the cache off agreed with the first on 93 of 100 letters, with 3 vs 3 discordant on correctness and the same 48%. Its picks (39 / 32 / 29) fit the true positions (p = 0.69). The spread is stable.

Sonnet's accuracy by position (51% / 40% / 53%) is not significantly different across positions (chi-square p = 0.50; goodness-of-fit of picks against the true positions p = 0.63). Haiku's middle-option preference holds under both greedy and default sampling, and it does not appear in Sonnet at its default sampling (Sonnet rejects temperature settings, so it was never run greedy). It is a property of the model, not of greedy decoding.

**Sampling regimes.** Haiku ran greedy (temperature 0) except where stated; Sonnet 5.5 and Opus 5.5 reject sampling parameters and ran at the API default. Haiku at temperature 0 is fully repeatable (100 of 100 letters identical across two runs); Sonnet at default sampling repeats 93 of 100.

**What a leaderboard would say vs what the data says.** A leaderboard would print 48 and 44 and rank them. The data says they are tied on this slice, and that one of the two is anchored on position while the other is not. The accuracy number alone cannot distinguish those.

## Majority-label baseline (computed 2026-10-04, no API calls)

The most common correct answer on `action_count` is the count "3": 41 of the first 100 items, 90 of all 200. A strategy that ignores the video and always answers "3" scores:

| Slice | Always "3" | Wilson 95% |
|---|---|---|
| first 100 items | 41% | [31.9%, 50.8%] |
| all 200 items | 45% | [38.3%, 51.9%] |

On the first 100 items that baseline sits inside every model's interval (Opus [42.3%, 61.5%], Sonnet [38.5%, 57.7%], Haiku [34.7%, 53.8%]). Whether any model beats its own content-free prior is phase 2's first question (H1, `docs/PHASE2_PLAN.md`). Note that the value prior ("3") and the position prior (middle slot) only partly coincide: "3" is an option on 75 of the first 100 items and sits at A / B / C on 29 / 27 / 19 of them, so Haiku's 59 middle picks are not explained by a preference for the value 3.

## Third model: Opus 5.5 at medium effort, same 100 items, 2026-10-04

Opus 5.5 cannot turn thinking off, so it ran with adaptive thinking at effort `medium` and `max_tokens` 4096. Sonnet and Haiku answered with no extended thinking. This is a comparison of shipped settings, not of matched compute. Output tokens: 8,223 over 100 items against about 1,000 for the other two, so the thinking was short.

| Model | Accuracy | Wilson 95% | Picks A/B/C | Acc by correct position A/B/C | Cost (uncached) |
|---|---|---|---|---|---|
| `claude-opus-5-5` (medium effort) | 52.0% | [42.3%, 61.5%] | 41 / 23 / 36 | 51% / 43% / 63% | $1.76 |
| `claude-sonnet-5-5` (between_tools) | 48.0% | [38.5%, 57.7%] | 39 / 31 / 30 | 51% / 40% / 53% | $0.81 |
| `claude-haiku-4-5-20251001` (t=0) | 44.0% | [34.7%, 53.8%] | 24 / 59 / 17 | 23% / 74% / 33% | $0.40 |

- **Opus vs Sonnet:** +4.0 points, bootstrap [-6.0, +14.0], discordant 15 vs 11, McNemar p = 0.56. **Tied.** One flip: 14 vs 12, p = 0.85.
- **Opus vs Haiku:** +8.0 points, bootstrap [-4.0, +21.0], discordant 25 vs 17, McNemar p = 0.28. **Tied.** One flip: 24 vs 18, p = 0.44.
- **Opus picks** lean away from the middle: 41 / 23 / 36 against 35 / 35 / 30 (goodness-of-fit p = 0.042). Accuracy by position is not significantly different (chi-square p = 0.26). The shuffled run below says whether that lean is positional.

**Opus shuffled (seed 1, 84 orders changed):** 51% [41.3%, 60.6%], picks 25 / 35 / 40 against 28 / 37 / 35 (goodness-of-fit p = 0.56). Of the 64 items whose first-run choice moved, Opus followed the answer text on 40, stayed on the letter on 13, and picked a third option on 11 (same-letter vs third, one-sided binomial p = 0.42, two-sided 0.84, as pre-registered: no position preference). Paired against its own unshuffled run: +1.0 point, 14 vs 13 discordant, p = 1.0, tied. The unshuffled lean away from the middle did not survive the reshuffle, so it was not positional. Opus follows content, less consistently than Sonnet (40 of 64 against 56 of 64), which fits a model answering with thinking at default sampling.

**Three models, one slice, no ranking.** 52, 48 and 44 on the same 100 items, every pairwise test tied, and none of the ten paired tests in this file survives Bonferroni (alpha 0.005). The one verdict at p < 0.05 (letters vs numbers) flips on a single item. What the data does support, with margins to spare: Haiku anchors on the middle option and the other two do not.

## Phase 2: what the label prior explains (2026-10-04 to 2026-10-07, pre-registered)

The hypotheses H1 to H6 below are phase 2's, from `docs/PHASE2_PLAN.md`. They are not the H3a to H3c checks earlier in this file.
- **Pre-registration:** I committed the plan as `ce30971` before the first paid run. The record is in `results/validation/preregistration.txt`.
- **H7, the human count:** I added it to the plan on 2026-10-06 as commit `515eb17`, before any counting. The record is in `results/validation/preregistration_h7.txt`.
- **Where those commits are:** this public repo starts from one cleaned commit. The commits that this repo names by hash are in my private development history. I can show them on request.
- **Source of every figure:** `scripts/handoff_analysis.py`, run on `results/*.jsonl`. A second, independent script recomputed each figure.
- **Option values for re-checking:** the figures that need option values use `results/validation/item_values.json`, which holds each item's answer and option numbers only.

**The short version:**
- **With no video at all,** each model scores about what "always answer 3" scores: 38%, 43% and 39% against 41%.
- **With option order averaged out,** only Opus beats that baseline: by 10.8 points [+1.7, +20.0], a margin that about 10 flipped answers in 600 would erase.
- **The no-video guesses differ by model.** Haiku leans on the middle slot. Sonnet and Opus lean on the value "3", the most common correct answer.
- **A person given the same 8 frames scores 8 of 20,** the same as "always 3" on those items. With the full clip the same person scores 20 of 20. The 8-frame input, not the models, is what cannot support the task.

### No frames at all (H1, H2)

A blind run asks the same 100 questions with the same options and no video frames.

| Model | Framed | Blind | Framed − blind | Blind picks middle | Blind picks "3" |
|---|---|---|---|---|---|
| Haiku 4.5 | 44% | 38% [29.1%, 47.8%] | +6.0 (23 vs 17, p = 0.43) | 62 / 100 | 25 / 100 |
| Sonnet 5.5 | 48% | 43% [33.7%, 52.8%] | +5.0 (26 vs 21, p = 0.56) | 41 / 100 | 64 / 100 |
| Opus 5.5 | 52% | 39% [30.0%, 48.8%] | +13.0 (25 vs 12, p = 0.047) | 35 / 100 | 65 / 100 |

- **H1 holds.** No model's framed run beats its blind run at the pre-registered alpha of 0.0167 (Bonferroni over three tests). Opus comes closest. One flipped item gives 26 vs 11, p = 0.020, which still holds. Two flips give p = 0.0076, which would falsify it.
- **H2 holds, narrowly.** The value-shuffled blind run reorders each item's options so that "3" never sits in the middle.
  - Haiku still picks the middle on 58 of 100 [48.2%, 67.2%].
  - On the 75 items that contain "3", it picks the middle 42 times and "3" 23 times (binomial p = 0.025).
  - The pre-registered "at least 50%" holds on the point estimate only; the interval includes 50%.
  - Against chance, which is one third, the middle preference is decisive (p = 6e-7).
- **Sonnet and Opus have the opposite prior.** In the value-shuffled run:
  - Sonnet picks "3" on 59 and the middle on 18. On the 75 items that contain "3": 59 vs 11.
  - Opus picks "3" on 62 and the middle on 14. On the 75 items: 62 vs 8.
  - With no video, they guess the most common answer, not the middle slot.

### All six option orderings (H3)

Each item was asked under all 6 orderings of its 3 options. Ordering 0 is the original order, from the phase 1 runs.
- **Permutation-averaged accuracy:** the mean over the 600 answers.
- **Consistency:** the share of items where the model picks the same option value under all 6 orderings.
- **Correct under all 6:** the CircularEval score.
- **Cramér's V:** how much the choice depends on the slot. 0 means not at all; 1 means always the same slot.

| Model | Permutation-averaged | Consistency | Correct under all 6 | Cramér's V | vs always "3", paired | Cost per correct |
|---|---|---|---|---|---|---|
| Haiku 4.5 | 37.7% [32.5%, 42.8%] | 14% | 6 / 100 | 0.369 | −3.3 [−12.8, +5.8] | $0.011 |
| Sonnet 5.5 | 45.0% [36.7%, 53.3%] | 59% | 31 / 100 | 0.043 | +4.0 [−6.5, +14.3] | $0.018 |
| Opus 5.5 | 51.8% [43.5%, 60.2%] | 52% | 30 / 100 | 0.062 | +10.8 [+1.7, +20.0] | $0.034 |

- **H3 is falsified as registered, by Opus alone.**
  - The registered criterion was that every permutation-averaged accuracy lies inside the baseline's Wilson interval, [31.9%, 50.8%].
  - Opus's 51.8% sits 7 answers in 600 above that.
  - The consistency part of H3 held for all three models.
- **The registered criterion is not a test of difference.** It compares one point estimate with one interval.
  - The paired comparison on the same items is the right test. For Opus it is +10.8 points [+1.7, +20.0], with sign-flip permutation p = 0.027 and Wilcoxon p = 0.019.
  - About 10 of Opus's 600 correct answers turning wrong would bring the lower bound to zero.
  - Haiku and Sonnet are not distinguishable from "always 3."
- **Haiku's choice depends on the slot** (V = 0.369, p = 4e-36). It is correct under all six orderings on only 6 items.
- **Opus's 52% consistency is limited by its own run-to-run variation.** Two runs of the same prompt with the cache off agree on 80 of 100 answers: 52% vs 50%, 9 vs 7 discordant, p = 0.80.

### 200 items (H4)

Items 101 to 200 were run in the original order and joined to the phase 1 runs.
- **Sonnet:** 101/200 = 50.5% [43.6%, 57.4%].
- **Haiku:** 84/200 = 42.0% [35.4%, 48.9%].
- **The comparison:** +8.5 points, bootstrap [−0.5, +17.5], discordant 52 vs 35, McNemar p = 0.086. **Tied.** One flip gives p = 0.053, still tied; two flips give p = 0.031.
- **Haiku's middle preference:** it picks the middle on 111 of 200 = 55.5% [48.6%, 62.2%].
- **The baseline:** always "3" scores 45% [38.3%, 51.9%] on the 200 items.

**H4 holds.**

### Frames (H5)

Haiku at 4 frames scored 42% [32.8%, 51.8%], at 8 frames 44%, and at 16 frames 39% [30.0%, 48.8%]. 4 vs 16 frames: +3.0 points, 15 vs 12 discordant, p = 0.70. **H5 holds:** across 4 to 16 frames, Haiku's accuracy on this task moves by less than 5 points.

### Harness parity with lmms-eval (H6): not run

A 1-item smoke test ran through lmms-eval 0.7.3, with two minimal fixes to its Claude wrapper, on the same video file. It showed that the task's 16-token reply cap cut Haiku off before it gave a letter. lmms-eval's scorer then read the article "a" in the cut-off sentence as option A, and scored the item correct. I stopped H6 there.
- **Evidence:** `results/validation/h6_not_run.md`.
- **Draft upstream issue, not filed:** `docs/upstream/lmms-eval-issue-draft.md`.

### Human count from the same frames (H7): falsified

Pre-registered on 2026-10-06 (`515eb17`), run on 2026-10-07 by me. The sheet shows 20 items from the first 100, chosen with seed 7 and stratified by the true answer value (8 × "3", 4 × "2", 3 × "4", 2 × "6", 2 × "7", 1 × "5"), each with the same 8 frames, question and option order the models saw on the unshuffled run, and no answers. The rule: H7 holds at 15 or more correct of 20, and is falsified at 14 or fewer.
- **Source:** `results/validation/human_count.csv` (the filled sheet) and `results/validation/human_count.json` (`scripts/human_count.py score`).

| Condition | Correct | Wilson 95% |
|---|---|---|
| Person, 8 frames only | 8 / 20 = 40.0% | [21.9%, 61.3%] |
| Person, full clip (the 12 misses rechecked) | 12 / 12 fixed, so 20 / 20 | |
| "Always 3" on the same 20 items | 8 / 20 | |
| Haiku 4.5, 8 frames, same 20 items | 8 / 20 | |
| Sonnet 5.5, 8 frames, same 20 items | 11 / 20 | |
| Opus 5.5, 8 frames, same 20 items | 8 / 20 | |

- **H7 is falsified, and not narrowly.** 8 of 20 is 7 items below the pass mark; one flipped item does not change the verdict.
- **The labels hold.** Every one of the 12 misses was corrected by watching the full clip, so none of them is a label error. The person's full-clip count agreed with the MVBench `answer` on all 12.
- **From 8 frames, the person scored what the models score.** 8 of 20, against Haiku 8, Opus 8 and Sonnet 11 on the same items, and against "always 3" at 8. The frames do not carry enough of the repeated action to count it.
- **The person's guesses are not the models' guesses.** By value, the picks were "4" × 6, "2" × 4, "3" × 4, "6" × 3, "1" × 2, "5" × 1; by letter A 10, B 4, C 6. Two notes say the count visible in the frames was below every option, so the lowest was chosen. A uniform 8-frame sample misses repetitions between frames, and the person undercounted. The models fill the same gap from their priors instead.
- **Confidence did not separate right from wrong.** Sure: 5 of 12 correct. Unsure: 3 of 8. Seven of the twelve "sure" answers were wrong. Two items were flagged as impossible from the frames; one of those was wrong.
- **Time:** 1,026 s for the 20-item frame pass, with one item at 413 s. The models answer in about a second.
- **Limits.** One person, 20 items, not blind to the hypothesis or the pass rule. Only the 8-frame input was checked by a person, so H5's flat 4-to-16-frame curve for Haiku has no human comparison at 16 frames.

### Cost

- **Billed:** phase 2 cost $17.10 of the $30 cap, by the spend gate.
- **Outside the gate:**
  - about $0.06 for 15 items that were paid for before a run stopped on low credit
  - about $0.01 for the lmms-eval smoke test
  - $0.004 for the Opus blind smoke test
- **Cost per correct answer** in the table above is at list price on every call's tokens, cached or not.
- **One cache miss:** the Haiku permutation runs re-paid for 84 items that should have come from the cache. All 84 answers matched the earlier answers exactly.

### What phase 2 changes

- **8 uniformly sampled frames cannot support this task.** A person given the same 8 frames the models saw counted 8 of 20 correctly, the same as "always 3" on those items (8), Haiku (8) and Opus (8), and near Sonnet (11). Given the full clip, the same person counted 20 of 20. The input, not the counting, is the limit.
- **The labels hold.** All 12 of the person's frame-only misses were corrected by the full clip. The benchmark's answers are right; its 8-frame rendering of the clips hides them.
- **The models' no-video scores are evidence about the benchmark.** With no frames at all, the three models score 38% to 43%, against 44% to 52% with 8 frames, and no model's gain passed the pre-registered test. A rule that never looks and always answers "3" scores 41%. Since a person cannot count from the same frames either, a score on this slice as configured measures mostly prior, for people and models alike. It does not show what any model does with video it can use.
- **With 8 frames, the models fill the gap from priors, in two different ways.** Haiku leans on position, the middle slot. Sonnet and Opus lean on value, the answer "3." The person undercounted instead. A single accuracy number shows none of this.
- **Averaged over option order, only Opus beats "always 3,"** by 10.8 points [+1.7, +20.0]; about 10 of its 600 answers turning wrong would erase that margin. Haiku (38%) and Sonnet (45%) cannot be told apart from the rule. Read against H7, Opus's margin is the one sign that a model got anything from these frames, and it is thin.
- **Phase 1's finding stands underneath this.** Even taking the scores at face value, 100 items cannot rank them; every pair is tied.
- **What this means for anyone using this benchmark:** before comparing models on an MVBench slice, check that a person can answer from the exact input the harness builds. For `action_count` at 8 frames, they cannot.

**Not yet measured:**
- Whether a person can count from 16 or 32 frames. That decides whether the models' flat 4-to-16-frame curve (H5) is about the models or still about sampling.
- Sonnet and Opus with more thinking (higher effort).
- Whether the position and value priors appear on other MVBench tasks.
- The paired comparison of Opus with the baseline on all 200 items, across all six orderings.
- Harness parity with lmms-eval.
