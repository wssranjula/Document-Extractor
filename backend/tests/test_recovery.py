from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import STAGE_NAMES, Document, Job, JobStage, Reference, User
from app.pipeline.nodes import build_nodes
from app.pipeline.recovery import STALE_ERROR, fail_running_job, fail_stale_jobs
from tests.test_authz import _reference_id, _signup


def _job(client, token: str) -> str:
    response = client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {token}"},
        data={"reference_id": _reference_id()},
        files={"file": ("discharge.docx", b"discharge text", "application/octet-stream")},
    )
    assert response.status_code == 201
    return response.json()["job_id"]


def _mark_running(job_id: str, *, seen_at: datetime) -> None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        job.status = "running"
        job.started_at = seen_at
        job.heartbeat_at = seen_at
        stage = session.scalar(select(JobStage).where(JobStage.job_id == job_id, JobStage.name == "parsed"))
        stage.status = "running"
        stage.started_at = seen_at
        session.commit()


def test_stale_running_job_fails_on_the_next_read(client):
    token = _signup(client, "stale@example.com")
    job_id = _job(client, token)
    _mark_running(job_id, seen_at=datetime.now(timezone.utc) - timedelta(minutes=5))

    response = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == STALE_ERROR
    parsed = next(stage for stage in body["stages"] if stage["name"] == "parsed")
    assert parsed["status"] == "failed"
    assert parsed["error"] == STALE_ERROR


def test_recent_heartbeat_keeps_the_job_running(client):
    token = _signup(client, "fresh@example.com")
    job_id = _job(client, token)
    _mark_running(job_id, seen_at=datetime.now(timezone.utc))

    response = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_done_stage_is_marked_succeeded_when_the_job_finishes(client):
    with SessionLocal() as session:
        user = User(email="done-stage@example.com", password_hash="hash")
        reference = Reference(name="Formulary", filename="reference.docx", storage_path="reference.docx")
        session.add_all([user, reference])
        session.flush()
        document = Document(
            user_id=user.id,
            reference_id=reference.id,
            filename="discharge.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            storage_path="discharge.docx",
        )
        session.add(document)
        session.flush()
        job = Job(document_id=document.id, user_id=user.id, status="running")
        session.add(job)
        session.flush()
        for position, name in enumerate(STAGE_NAMES):
            session.add(JobStage(job_id=job.id, name=name, position=position, status="pending"))
        session.commit()
        job_id = job.id
        build_nodes(session)["done"]({"job_id": job_id})

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        done = session.scalar(select(JobStage).where(JobStage.job_id == job_id, JobStage.name == "done"))
        assert job.status == "succeeded"
        assert done.status == "succeeded"
        assert done.finished_at is not None


def test_failed_job_is_not_failed_again(client):
    token = _signup(client, "done@example.com")
    job_id = _job(client, token)
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        job.status = "failed"
        job.error = "Already recorded"
        session.commit()

    with SessionLocal() as session:
        fail_running_job(session, job_id, "Verification stopped unexpectedly.")
        fail_stale_jobs(session)

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job.status == "failed"
        assert job.error == "Already recorded"
