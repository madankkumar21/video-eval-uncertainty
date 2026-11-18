# Video brief: what one accuracy number hides

Input for `/explainer-video`. The video is a recap of what this repo's test found and why it matters. Technical depth is fine.

Every number below has been verified against `results/*.jsonl` and `results/handoff_analysis.json` at commit `041c36c`. Do not round, drop or change a number, interval, p-value or label. If a scene needs a number that isn't here, leave it out.

## Thesis

On a public video benchmark, one accuracy number per model can't rank these three models, and it hides how each model gets its answers.

## Setup (show once, briefly)

- **Benchmark:** MVBench `action_count`, "how many times did the person do X?". Three answer options, so chance is 33.3%.
- **Items:** the first 100 of the task's 200 items, 8 frames per video. Every model answered the same 100 items.
- **Models:**
  - Haiku 4.5 at temperature 0
  - Sonnet 5.5 with thinking off (`between_tools`)
  - Opus 5.5 at medium effort
- **Statistics:**
  - a 95% Wilson interval on each accuracy
  - paired McNemar tests on the items where two models disagree
  - a bootstrap interval on each difference

## Scenes

1. **The question.** A leaderboard says model A scores 85% and model B scores 84%. Is that a difference, or noise?

2. **The headline.** Three bars with error bars:

   | Model | Accuracy | 95% interval |
   |---|---|---|
   | Opus 5.5 | 52% | [42.3%, 61.5%] |
   | Sonnet 5.5 | 48% | [38.5%, 57.7%] |
   | Haiku 4.5 | 44% | [34.7%, 53.8%] |

   The intervals overlap heavily. Every pair is **tied**:
   - Opus vs Sonnet: p = 0.56
   - Sonnet vs Haiku: p = 0.64
   - Opus vs Haiku: p = 0.28

   Ten paired tests were run in total. None survives a Bonferroni correction (alpha 0.005).

3. **How many items it would take.** These are estimates. Label them "estimate" on screen. They assume 80% power, alpha 0.05, and each pair's observed disagreement rate.

   | Gap to detect | Items needed |
   |---|---|
   | 8 points (Opus vs Haiku) | about 510 |
   | 4 points (Opus vs Sonnet) | about 1,270 |
   | 4 points (Sonnet vs Haiku) | about 2,060 |

   The whole task has **200**. The benchmark is too small to rank these models at these gaps.

4. **What the number hides: Haiku guesses the middle.**
   - The correct answer is in the middle on 35 of 100 items. Haiku picks the middle 59 times.
   - Accuracy by where the right answer sits: A 23%, B 74%, C 33%.
   - At default temperature Haiku still picks the middle 55 times, so greedy decoding isn't the cause.

5. **The shuffle test.** Reshuffle the options under the same letters. On the 62 items where Haiku's chosen option moved:
   - It **followed the answer** on 28.
   - It **stayed on the same letter** on 28.
   - It switched to the third option on 6.

   Show one item animating: the content moves and the pick stays on B.

6. **The contrast.**
   - **Sonnet** followed the answer on **56 of 64** moved items. Two separate Sonnet runs agreed on 93 of 100 answers.
   - **Opus** followed the answer on **40 of 64**. It shows no position preference: 13 same-letter vs 11 third-option, one-sided p = 0.42.

   Similar scores, very different behavior.

7. **A fragile result.** Labelling the options 1/2/3 instead of A/B/C dropped Haiku from 44% to 35% (p = 0.022). One item flipping makes that a tie (p = 0.092). It is still a real effect: Haiku repeated all 100 of its answers exactly, so the gap isn't sampling noise. It is too small for 100 items to pin down.

8. **So what.** Before trusting "model A beats model B by N points," ask three questions:
   1. What are the intervals?
   2. How many items would a gap that size need?
   3. Does the score survive shuffling the options?

   This repo answers all three for any model on any MVBench slice.

## Guardrails

- **Never say or imply that Opus is best.** "52 > 48 > 44" is not a ranking.
- **"Tied" means "not distinguishable on this data,"** not "identical."
- **Keep the scope on screen:** 100 items, one task.
- **The cost line, if used:** about $6.26 billed across all ten runs. Leave cost out if the video has no natural place for it.
- **Out of scope:** the Temporal and crash-test story, and the engine comparison.

## Rendered

2026-10-04, `what-one-number-hides.mp4`, 179.7 s, built locally with the `/explainer-video` toolkit (Manim, Kokoro voice, Whisper check). The 12 review frames (one every 15 s) are in `docs/video-frames/`; the narration and scene source are in `docs/video-source/`, so every on-screen number can be checked from text. Transcript check: every number spoken as written; two Whisper mishearings only ("in all" heard as "and all", "N points" as "endpoints"). The $6.26 cost line was left out, as the brief allows. The mp4 (9.9 MB) is not committed.


---

# Version 2 brief: the no-video score (not yet rendered)

Supersedes the thesis above for any re-render. Scenes 1 to 8 above remain accurate; v2 reorders them around phase 2 and adds the field opening. Every number below is verified against `results/*.jsonl`, `results/handoff_analysis.json` and `results/validation/item_values.json` at commit `d2f63fc`. Same rule: do not round, drop or change a number.

## Thesis (v2)

On this video benchmark, most of each model's score does not come from the video. Taking the frames away barely moves the number, and a rule that always gives the most common answer scores in the same band. One accuracy number hides that, and hides how each model fills the gap.

## Scenes (v2)

1. **The field opening (10 s, no numbers).** A contextual advertising use case at work. Contextual advertising places an ad beside content that matches a brief. The tagging agent dropped an exclusion that the brief required. The builder only knew by watching the clips. A rerun returned different scenes. Someone asked "how do you know the tags are right?" There was a process to show and no number.

2. **With and without the video.** Two bars per model.

   | Model | With video | Without video |
   |---|---|---|
   | Opus 5.5 | 52% | 39% |
   | Sonnet 5.5 | 48% | 43% |
   | Haiku 4.5 | 44% | 38% |

   A horizontal line at 41%: "always answer 3." Caption: no model's gain from the video passed the pre-registered test (alpha 0.0167; Opus p = 0.047, Haiku 0.43, Sonnet 0.56).

3. **How a model scores 38% with no video.** Two habits, animated.
   - Haiku picks the middle slot: 62 of 100 blind, 58 of 100 when "3" is kept out of the middle.
   - Sonnet and Opus pick "3": 59 and 62 of 100 when "3" is kept out of the middle.
   - "3" is correct on 41 of 100 items.

4. **Averaged over all six orderings.**

   | Model | Averaged | vs "always 3", paired |
   |---|---|---|
   | Haiku 4.5 | 37.7% [32.5%, 42.8%] | −3.3 [−12.8, +5.8] |
   | Sonnet 5.5 | 45.0% [36.7%, 53.3%] | +4.0 [−6.5, +14.3] |
   | Opus 5.5 | 51.8% [43.5%, 60.2%] | +10.8 [+1.7, +20.0] |

   Caption: Opus clears the rule by 10.8 points; about 10 of its 600 answers turning wrong would erase the margin. Consistency across orderings: Haiku 14, Sonnet 59, Opus 52 of 100.

5. **A rerun is a second draw.** Opus agreed with itself on 80 of 100; Sonnet on 93 of 100; Haiku at temperature 0 on 100 of 100.

6. **Phase 1 underneath (reuse scenes 2 and 3 above).** Every pair tied; a 4-point gap needs about 1,300 to 2,000 items; the task has 200.

7. **The four questions.** No-video score. Most-common-answer score. Items and margin. Shuffled options.

8. **What a person scores from the same frames (H7, run 2026-10-07).** 8 of 20, Wilson [21.9%, 61.3%], against a pre-registered pass mark of 15. "Always 3" scores 8 of those 20; Haiku 8, Opus 8, Sonnet 11. With the full clip the person corrected all 12 misses. The headline for any re-render is therefore "8-frame sampling cannot support this task, and the no-video scores show what a score here is made of," not "the models don't use the video." Scope: one task, 100 clips, one person on 20 items.

## Guardrails (v2, in addition to the above)

- Never say the models "cannot understand video." Say "on this task, taking the video away barely changed the scores."
- The field opening names no brand, network, customer, content type or dataset size. It says only "a contextual advertising use case at work".
- Label the paired "vs always 3" interval as the test of difference; the registered H3 criterion compared a point to the baseline's interval and is reported as falsified in RESULTS.md.
