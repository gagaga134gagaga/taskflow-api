import asyncio

from sqlalchemy import select

from app.broker import publish
from app.db import SessionLocal
from app.models import Job


async def main():
    with SessionLocal() as db:
        ids = db.scalars(select(Job.id).where(Job.status == "pending")).all()
    for job_id in ids:
        await publish(job_id)
    print(f"Republished {len(ids)} pending jobs")


if __name__ == "__main__":
    asyncio.run(main())
