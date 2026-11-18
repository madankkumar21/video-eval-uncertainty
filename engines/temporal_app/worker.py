"""Start a worker. Kill it mid-run (scenario 2) and start it again; the workflow resumes."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from . import TASK_QUEUE
from .activities import answer_item_activity, publish_activity, summarize_activity
from .workflows import EvalWorkflow


async def main() -> None:
    client = await Client.connect(os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"))
    with ThreadPoolExecutor(max_workers=4) as executor:
        worker = Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[EvalWorkflow],
            activities=[answer_item_activity, summarize_activity, publish_activity],
            activity_executor=executor,
            max_concurrent_activities=2,
        )
        print(f"worker up on '{TASK_QUEUE}' (pid {os.getpid()})", flush=True)
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
