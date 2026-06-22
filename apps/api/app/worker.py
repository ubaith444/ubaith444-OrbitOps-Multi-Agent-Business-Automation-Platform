"""Worker process entrypoint.

Production deployments replace the polling boundary with a Redis Streams or SQS consumer.
The API remains the sole writer of workflow intent; workers execute idempotently by run id.
"""

import asyncio

import structlog

from app.core.database import SessionLocal
from app.services.communications import process_due_retries

log = structlog.get_logger()


async def main() -> None:
    log.info("worker_started")
    while True:
        try:
            async with SessionLocal() as db:
                processed = await process_due_retries(db)
            log.info("worker_heartbeat", communication_retries=processed)
        except Exception as exc:
            log.exception("worker_cycle_failed", error=str(exc))
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
