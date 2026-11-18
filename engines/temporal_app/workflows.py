"""The workflow: iterate items, retry per item, wait for a human, publish.

Workflow code must be deterministic, so it only sequences activities. All I/O,
numpy and the Anthropic SDK live in activities.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import answer_item_activity, publish_activity, summarize_activity
    from .shared import EvalParams, ItemCall, RunSummary

# Scenario 1: rate limits. Exponential backoff, capped; fatal errors never retry.
MODEL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=8,
    non_retryable_error_types=["Fatal"],
)


@workflow.defn
class EvalWorkflow:
    def __init__(self) -> None:
        self.params: EvalParams | None = None
        self.decision: str | None = None
        self.progress: int = 0
        self.summary: RunSummary | None = None

    @workflow.signal
    def approve(self, decision: str) -> None:
        """Scenario 3: a person decides whether the results publish."""
        self.decision = decision

    @workflow.query
    def status(self) -> dict:
        return {
            "progress": self.progress,
            "n": self.params.n if self.params else None,
            "waiting_for_approval": self.summary is not None and self.decision is None,
            "decision": self.decision,
            "summary": self.summary.__dict__ if self.summary else None,
        }

    @workflow.run
    async def run(self, params: EvalParams) -> dict:
        self.params = params
        rows = list(params.rows)
        self.progress = params.start_index

        for i in range(params.start_index, params.n):
            # Scenario 2: each completed activity is journaled in the workflow history.
            # If the worker dies, replay skips finished items and resumes here.
            row = await workflow.execute_activity(
                answer_item_activity,
                ItemCall(params.run_id, params.model_id, params.task, i, params.n_frames,
                         params.shuffle_seed, params.label_style),
                start_to_close_timeout=timedelta(seconds=180),
                heartbeat_timeout=timedelta(seconds=90),
                retry_policy=MODEL_RETRY,
            )
            rows.append(row)
            self.progress = i + 1

            # Scenario 5: history has a hard limit (51,200 events). Hand the state to a
            # fresh run before we get there.
            next_i = i + 1
            if next_i < params.n and (
                next_i % params.chunk == 0 or workflow.info().is_continue_as_new_suggested()
            ):
                workflow.continue_as_new(
                    EvalParams(**{**params.__dict__, "start_index": next_i, "rows": rows})
                )

        self.summary = await workflow.execute_activity(
            summarize_activity, rows, start_to_close_timeout=timedelta(seconds=60)
        )

        # Scenario 3: block until a person signals. The run survives worker restarts while waiting.
        await workflow.wait_condition(lambda: self.decision is not None)
        if self.decision != "yes":
            return {"published": False, "decision": self.decision, "summary": self.summary.__dict__}

        path = await workflow.execute_activity(
            publish_activity, args=[params.run_id, rows], start_to_close_timeout=timedelta(seconds=60)
        )
        return {"published": True, "path": path, "summary": self.summary.__dict__}
