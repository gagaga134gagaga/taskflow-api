import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.broker import publish
from app.config import settings
from app.db import get_db
from app.models import Job, JobEvent
from app.schemas import EventView, JobCreate, JobView
from app.service import add_event

app = FastAPI(title="TaskFlow API", version="1.0.0", description="Durable asynchronous job processing API")


def authorize(x_api_key: str = Header(default="")):
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "ok"}


@app.post("/v1/jobs", response_model=JobView, status_code=202, dependencies=[Depends(authorize)])
async def create_job(body: JobCreate, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128), db: Session = Depends(get_db)):
    existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
    payload = body.model_dump_json()
    if existing:
        if existing.payload != payload:
            raise HTTPException(409, "Idempotency key used for different payload")
        return existing
    job = Job(idempotency_key=idempotency_key, payload=payload)
    db.add(job)
    db.flush()
    add_event(db, job, "pending", "Accepted")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing and existing.payload == payload:
            return existing
        raise HTTPException(409, "Idempotency conflict") from None
    db.refresh(job)
    try:
        await publish(job.id)
    except Exception:
        # Job remains pending and can be republished via the recovery command.
        raise HTTPException(503, detail=f"Job {job.id} stored; broker unavailable. Retry with the same Idempotency-Key") from None
    return job


@app.get("/v1/jobs", response_model=list[JobView], dependencies=[Depends(authorize)])
def list_jobs(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    return db.scalars(select(Job).order_by(Job.created_at.desc()).limit(limit)).all()


@app.get("/v1/jobs/{job_id}", response_model=JobView, dependencies=[Depends(authorize)])
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/v1/jobs/{job_id}/events", response_model=list[EventView], dependencies=[Depends(authorize)])
def get_events(job_id: str, db: Session = Depends(get_db)):
    if db.get(Job, job_id) is None:
        raise HTTPException(404, "Job not found")
    return db.scalars(select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.id)).all()
