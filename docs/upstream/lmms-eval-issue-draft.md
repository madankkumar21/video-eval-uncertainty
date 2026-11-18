# Issue for EvolvingLMMs-Lab/lmms-eval: filed as [#1694](https://github.com/EvolvingLMMs-Lab/lmms-eval/issues/1694)

Filed on 2026-11-18. The text below is the filed text.

Checked on 2026-11-18 against `main` at `c33a160d` by reading the code. Both behaviors are still present. A search of issues and pull requests found no duplicate. The closest is #1688, the same failure in geometry3k, with its fix in #1689.

---

**Title:** MVBench: a 16-token cap cuts off replies, and `mcq_acc` then scores the article "a" as option A

**Bug Description**

Two behaviors in the MVBench task combine to score a non-answer as option A.

1. **The cap.** `_default_template_yaml` sets `max_new_tokens: 16` for every MVBench subtask ([line 9](https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/c33a160d7d08168897051091029aee2d88229232/lmms_eval/tasks/mvbench/_default_template_yaml#L9)). Chat models often describe the frames before they give a letter, so the cap cuts the reply before the answer.
2. **The fallback.** `mcq_acc` first calls `extract_final_mcq_answer` ([line 140](https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/c33a160d7d08168897051091029aee2d88229232/lmms_eval/tasks/mvbench/utils.py#L140)). A cut-off reply states no answer, so that step returns `""` and the old parser runs. The old parser lowercases the reply ([line 131](https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/c33a160d7d08168897051091029aee2d88229232/lmms_eval/tasks/mvbench/utils.py#L131)). Then it searches for any single letter A to E, ignoring case ([line 134](https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/c33a160d7d08168897051091029aee2d88229232/lmms_eval/tasks/mvbench/utils.py#L134)). In an English sentence, the first match is usually the article "a".

The result: a cut-off reply scores as correct when the ground truth is A, and as wrong when it is B to E. `mvbench_aggregate_results` excludes only empty predictions ([line 187](https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/c33a160d7d08168897051091029aee2d88229232/lmms_eval/tasks/mvbench/utils.py#L187)), so the reply also counts as answered.

**Steps to Reproduce**

I ran one item on 0.7.3: `mvbench_action_count`, `doc_id` 0, with the `claude` model and `claude-haiku-4-5-20251001`. This is the logged sample, trimmed:

```
"input": "Question:How many times did the person launch objects on the table?\nOption:\n(A) 3\n(B) 2\n(C) 4\nOnly give the best option.\n"
"filtered_resps": "Looking at the sequence of images, I can see a person's hand appearing in"
"token_counts": [{"input_tokens": 9642, "output_tokens": 16}]
"mvbench_accuracy": {"pred_answer": "Looking at the sequence of images, I can see a person's hand appearing in", "gt_answer": "A", "score": 1}
```

The same result comes from calling the function directly on 0.7.3:

```
mcq_acc("A", "Looking at the sequence of images, I can see a person's hand appearing in")  -> 1
mcq_acc("B", "Looking at the sequence of images, I can see a person's hand appearing in")  -> 0
mcq_acc("A", "The video shows a person")                                                   -> 1
```

On `main` I did not run the task. I read the code: the cap is unchanged, and #1656 keeps the old parser for every reply that `extract_final_mcq_answer` does not read, "so those responses score as before".

**Expected**

A reply that hits the token cap without stating an option should count as unanswered or wrong, never as correct. Free text that names no option should not map to A.

**Suggested fixes**

- **Raise `max_new_tokens`** for MVBench, or make it configurable per model. The prompt could also ask for the letter alone.
- **Make the fallback strict.** Accept a letter only when the reply is a bare choice (`B`, `(B)`, `B.`). Otherwise score the reply as unparsed, and report the unparsed count next to the accuracy.
- **Note on the #1689 approach.** A capital-only pattern does not work here as it stands. `process` lowercases the reply before the search, so a capital-only search would also miss a plain `B`. The check has to run before the lowercase step.
- **Optionally, flag a reply as truncated** when its output token count equals `max_new_tokens`.

**Environment**

- lmms-eval 0.7.3 for the run; `main` at `c33a160d` checked by reading the code
- Task: `mvbench_action_count`
- Model: `claude` wrapper, `claude-haiku-4-5-20251001`, `anthropic` 0.125.0
- OS: macOS

**Additional Context**

- Related: #1688 and #1689 (geometry3k, same failure with the article "a").
- Separate from this bug: `models/simple/claude.py` sends both `temperature` and `top_p` ([line 213](https://github.com/EvolvingLMMs-Lab/lmms-eval/blob/c33a160d7d08168897051091029aee2d88229232/lmms_eval/models/simple/claude.py#L213)). Anthropic's API reference says that Claude 4.x models accept only one of them. I can file this on its own.
- I found this while building a paired-uncertainty evaluation of frontier models on MVBench `action_count`: https://github.com/madankkumar21/video-eval-uncertainty
