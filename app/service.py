import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Job, JobEvent


def add_event(db: Session, job: Job, status: str, message: str):
    job.status = status
    db.add(JobEvent(job_id=job.id, status=status, message=message))


def calculate(payload: str) -> str:
    data = json.loads(payload)
    text = data["text"]
    if data["operation"] == "word_count":
        return json.dumps({"words": len(text.split()), "characters": len(text)})
    if data["operation"] == "checksum":
        return json.dumps({"sha256": hashlib.sha256(text.encode()).hexdigest()})
    raise ValueError("Unsupported operation")


def process_job(db: Session, job_id: str) -> str:
    # Row lock serializes duplicate deliveries in PostgreSQL.
    job = db.execute(select(Job).where(Job.id == job_id).with_for_update()).scalar_one_or_none()
    if job is None:
        return "missing"
    if job.status in {"completed", "failed"}:
        return "already_final"
    job.attempts += 1
    add_event(db, job, "processing", f"Attempt {job.attempts}")
    try:
        job.result = calculate(job.payload)
    except Exception as exc:
        job.error = str(exc)[:500]
        if job.attempts >= settings.max_attempts:
            add_event(db, job, "failed", "Retry limit reached")
        else:
            add_event(db, job, "pending", "Scheduled for retry")
    else:
        job.error = None
        add_event(db, job, "completed", "Result stored")
    db.commit()
    return job.status
