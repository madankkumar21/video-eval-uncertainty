"""Temporal adapter: one workflow per run, one activity per model call.

  temporal server start-dev --db-filename results/temporal.db
  uv run python -m engines.temporal_app.worker
  uv run python -m engines.temporal_app.run start --model stub --n 10 --run-id demo
  uv run python -m engines.temporal_app.run status --run-id demo
  uv run python -m engines.temporal_app.run approve --run-id demo --decision yes
"""

TASK_QUEUE = "video-eval"
