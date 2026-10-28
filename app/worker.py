import asyncio
import logging

from app.broker import connect, declare, publish
from app.db import SessionLocal
from app.service import process_job

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def main():
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await declare(channel)
        log.info("Worker ready")
        async with queue.iterator() as messages:
            async for message in messages:
                async with message.process(requeue=True):
                    job_id = message.body.decode()
                    with SessionLocal() as db:
                        state = process_job(db, job_id)
                    if state == "pending":
                        # Retry with a delay; a duplicate delivery is safe.
                        await asyncio.sleep(2)
                        await publish(job_id)


if __name__ == "__main__":
    asyncio.run(main())
