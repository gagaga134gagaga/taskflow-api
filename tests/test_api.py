from unittest.mock import AsyncMock

from app.config import settings
from app.models import Job
from app.service import process_job

HEADERS = {"X-API-Key": settings.api_key, "Idempotency-Key": "unique-key-123"}


def test_health(client):
    assert client.get("/health/live").json() == {"status": "ok"}


def test_auth_required(client):
    assert client.get("/v1/jobs").status_code == 401


def test_create_and_process(client, db, monkeypatch):
    monkeypatch.setattr("app.main.publish", AsyncMock())
    response = client.post("/v1/jobs", headers=HEADERS, json={"operation": "word_count", "text": "hello world"})
    assert response.status_code == 202
    job_id = response.json()["id"]
    assert process_job(db, job_id) == "completed"
    assert client.get(f"/v1/jobs/{job_id}", headers=HEADERS).json()["status"] == "completed"
    assert len(client.get(f"/v1/jobs/{job_id}/events", headers=HEADERS).json()) == 3
    assert process_job(db, job_id) == "already_final"


def test_idempotency(client, monkeypatch):
    publisher = AsyncMock()
    monkeypatch.setattr("app.main.publish", publisher)
    data = {"operation": "checksum", "text": "abc"}
    a = client.post("/v1/jobs", headers=HEADERS, json=data)
    b = client.post("/v1/jobs", headers=HEADERS, json=data)
    assert a.json()["id"] == b.json()["id"]
    assert publisher.await_count == 1
    c = client.post("/v1/jobs", headers=HEADERS, json={"operation": "checksum", "text": "different"})
    assert c.status_code == 409


def test_invalid_input(client):
    response = client.post("/v1/jobs", headers=HEADERS, json={"operation": "invalid", "text": "abc"})
    assert response.status_code == 422


def test_missing_job(client):
    assert client.get("/v1/jobs/nope", headers=HEADERS).status_code == 404


def test_broker_outage_is_recoverable(client, db, monkeypatch):
    monkeypatch.setattr("app.main.publish", AsyncMock(side_effect=ConnectionError("offline")))
    response = client.post("/v1/jobs", headers=HEADERS, json={"operation": "checksum", "text": "abc"})
    assert response.status_code == 503
    assert db.query(Job).count() == 1
    assert db.query(Job).first().status == "pending"


def test_retry_and_failure(db, monkeypatch):
    from app import service
    from app.models import Job
    monkeypatch.setattr(service, "calculate", lambda payload: (_ for _ in ()).throw(ValueError("bad")))
    job = Job(idempotency_key="key-12345678", payload='{"operation":"checksum","text":"abc"}')
    db.add(job)
    db.commit()
    for _ in range(settings.max_attempts - 1):
        assert process_job(db, job.id) == "pending"
    assert process_job(db, job.id) == "failed"
    assert process_job(db, job.id) == "already_final"
