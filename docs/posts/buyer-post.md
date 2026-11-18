# Ask for the no-video score, and check the input first

*How to read a video-AI benchmark before you buy. Every figure is from `RESULTS.md` in this repo.*

Contextual advertising places an ad beside content that matches a brief. At work I built contextual advertising packages on video content. The tagging agent dropped an exclusion that the brief required. I only knew because I watched the clips. A rerun returned different scenes. Someone asked how I knew the tags were right. I had a process to show and no number.

I kept thinking about the question I could not answer. This repo is what I built to answer it, on public data, with public models, for about $25 in API calls.

## What a benchmark score hides

A video benchmark asks a model a question about a clip and marks the answer right or wrong. Here is what three current models scored on one task, counting how many times a person repeats an action, over the same 100 clips. The harness gives the model 8 still frames from each clip, spread evenly through it.

| Model | With the 8 frames | Without them |
|---|---|---|
| Opus 5.5 | 52% | 39% |
| Sonnet 5.5 | 48% | 43% |
| Haiku 4.5 | 44% | 38% |
| Always answer "3" | 41% | 41% |

The second column is the same question and options with no frames at all. The last row is a rule that ignores everything and gives the most common correct answer.

Taking the frames away cost each model 5 to 13 points. None of those gaps passed the threshold we set before running the test. The rule that never looks scores inside the same band. My first reading was that the models were not using the video. The next check corrected that.

## What a person scores from the same frames

I took 20 of the clips, chosen in advance to cover the range of right answers, and counted the actions myself from the same 8 frames the models saw, with no answers on the sheet. The pass mark was written down first: 15 of 20 and the models were the problem.

I scored 8 of 20. "Always 3" scores 8 of 20 on those same clips. Haiku scored 8, Opus 8, Sonnet 11.

Then I watched the full clips for the 12 I had missed and corrected all 12. The benchmark's answers are right. Its 8-frame rendering of the clips hides them: a repetition between two sampled frames is invisible, and I undercounted, sometimes below every option on offer.

So the no-video score was telling the truth, about the benchmark. On this task as the harness builds it, there is little in the input to count from, for me or for the models. A leaderboard number here measures mostly what each model guesses when it cannot see.

## How a model guesses when it cannot see

The models are not guessing at random. Each one has a habit. Haiku picks the middle option: with the frames removed and the options rearranged so the common answer was never in the middle, it still picked the middle 58 times in 100. Sonnet and Opus pick the most common answer: in the same run they chose "3" on 59 and 62 of 100 items, and "3" is right 41% of the time. I undercounted instead. Different habit, same score.

This is the benchmark version of the exclusion that my tagging agent dropped. When the evidence does not settle the answer, the output still looks like a judgment. Some of it is a default.

## Averaging out the shortcuts

A multiple-choice score depends on where the right answer sits, so we asked every question six times, once per ordering of its options, and averaged.

| Model | Averaged over all orderings | Against "always 3", same items |
|---|---|---|
| Haiku 4.5 | 38% | −3 points, not distinguishable |
| Sonnet 5.5 | 45% | +4 points, not distinguishable |
| Opus 5.5 | 52% | +11 points [+2, +20] |

Only Opus beats the rule that never looks, and the margin is thin: about 10 of its 600 answers turning wrong would erase it. Given what a person can do with these frames, that margin is the one sign that any model got something from them.

## Why one run is not a measurement

Two runs of the same prompt gave Opus the same answer on 80 of 100 items and Sonnet on 93. A rerun is a second draw, not a check. Confirming a 4-point gap between two models here would take roughly 1,300 to 2,000 questions; the task has 200. Every pair is a statistical tie on 100 items, and a leaderboard would rank them anyway.

## Five questions for any video benchmark

Ask these before trusting a vendor's number, or your own.

1. **Can a person do the task from the exact input the model gets?** The frames, the resolution, the prompt, not the clip. If a person cannot, the score is not about the model.
2. **What does the model score with the video removed?** The gap is how much of the score the input earned. Here it was 5 to 13 points.
3. **What does "always give the most common answer" score?** Within a few points of it, the score is mostly prior.
4. **How many items, and what is the margin?** 100 items gives an interval about 20 points wide. Overlapping models are tied.
5. **Does the score hold when the options are shuffled?** If it falls, the model is reading the layout.

Every one of these is cheap. The person check took me 17 minutes for 20 items. The no-video run costs a tenth of the framed run. The shuffle costs the same as the original. The baseline costs nothing.

## What this does not show

One task, one hundred clips, one person on twenty of them. It does not show what these models do with video they can use: more frames, or the clip itself. Going from 4 to 16 frames did not move Haiku, but nobody has checked whether a person can count from 16 either. The benchmark's answers are not wrong; they cannot be reached from the input it builds for this task.

## Try it on your own footage

The repo runs these checks against any multiple-choice video task, with intervals on every number, a paired test between two models, and a blind sheet for the person check. The next time someone asks how I know the tags are right, I want a number, and I want them to have one too. The first one is the simplest: could a person have got this from what the model was shown?

*Repo: `video-eval-uncertainty`. Figures: `RESULTS.md`, phase 1 and phase 2 sections. Pre-registered hypotheses and spend: `docs/PHASE2_PLAN.md`. The person check: `results/validation/human_count.json`.*
