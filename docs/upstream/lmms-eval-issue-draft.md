# Draft issue for EvolvingLMMs-Lab/lmms-eval (not filed)

I have not filed this yet. Before filing:
- check that `main` still has both behaviors; this was checked against the 0.7.3 wheel only
- search the existing issues for duplicates

---

**Title:** MVBench: a 16-token cap truncates API-model replies, and `mcq_acc` scores the article "a" as option A

**Version:** lmms-eval 0.7.3, tasks `mvbench_*`. All of them include `tasks/mvbench/_default_template_yaml`.

**What happens**

1. `_default_template_yaml` sets `generation_kwargs.max_new_tokens: 16`. Chat-style API models often describe the frames before they give a letter, so the cap cuts the reply off before the answer.
2. `utils.mcq_acc` falls back to `re.search(r"\b([A-E])\b", answer, re.IGNORECASE)` on free text. In a cut-off English sentence, the first match is usually the article "a", so the reply is scored as option A.

Together, these turn a non-answer into a correct answer whenever the ground truth is A. They also count it as answered, because `mvbench_aggregate_results` only excludes empty predictions. When the ground truth is B to E, the same reply is scored wrong instead of unanswered.

**Reproduction.** One item, `mvbench_action_count`, `doc_id` 0, with the `claude` model wrapper and `claude-haiku-4-5-20251001`. Two local fixes to the wrapper were needed to run it at all; they are listed under "Related" below. This is the logged sample, trimmed:

```
"input": "Question:How many times did the person launch objects on the table?\nOption:\n(A) 3\n(B) 2\n(C) 4\nOnly give the best option.\n"
"filtered_resps": "Looking at the sequence of images, I can see a person's hand appearing in"
"token_counts": [{"input_tokens": 9642, "output_tokens": 16}]
"mvbench_accuracy": {"pred_answer": "Looking at the sequence of images, I can see a person's hand appearing in", "gt_answer": "A", "score": 1}
```

The same result comes from calling the function directly:

```
mcq_acc("A", "Looking at the sequence of images, I can see a person's hand appearing in")  -> 1
mcq_acc("B", "Looking at the sequence of images, I can see a person's hand appearing in")  -> 0
mcq_acc("A", "The video shows a person")                                                   -> 1
```

**Expected.** A reply that hit the token cap without stating an option should be counted as unanswered or wrong, never as a correct answer. Free text that doesn't name an option should not map to A.

**Suggested fixes** (happy to open a PR for whichever you prefer):
- **Raise `max_new_tokens`** for MVBench, or make it configurable per model. The prompt could also ask for the letter alone ("Answer with the option's letter only.").
- **Make the fallback in `mcq_acc` strict.** Accept a letter only when the reply starts with it (`B`, `(B)`, `B.`). Otherwise score the reply as unparsed, and report the count of unparsed replies next to the accuracy.
- **Optionally, flag a reply as truncated** when its output token count equals `max_new_tokens`.

**Related, separate from the scoring bug** (in `models/simple/claude.py`, 0.7.3). These can go in their own issue:
- **Sampling parameters:** `client.messages.create` sends both `temperature` and `top_p`. Anthropic's API reference says Claude 4.x models accept at most one of them.
- **The decord import:** `anthropic` and `decord` are imported in the same `try` block. lmms-eval doesn't install decord on macOS (`platform_system != "Darwin"`), so on a Mac the Claude client never imports. Reading frames with PyAV, which is already a core dependency, avoids this. A patch is in this repo at `patches/lmms-eval-0.7.3-claude.patch`.
- **The SDK version:** with `anthropic` 1.x installed, `messages.create` no longer accepts `temperature` as a keyword, and the wrapper fails before sending a request. Pinning `anthropic<1.0` works around it.

Found while building a paired-uncertainty evaluation of frontier models on MVBench `action_count`: `<repo link once public>`.
