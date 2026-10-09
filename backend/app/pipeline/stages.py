import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobStage

logger = logging.getLogger("app.pipeline")
_ERROR_LIMIT = 2000


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_stage(session: Session, job_id: str, name: str, work):
    _set_running(session, job_id, name)
    try:
        result = work()
    except Exception as exc:
        _set_failed(session, job_id, name, exc)
        raise
    _set_succeeded(session, job_id, name)
    return result


def _stage(session: Session, job_id: str, name: str) -> JobStage:
    stage = session.scalar(select(JobStage).where(JobStage.job_id == job_id, JobStage.name == name))
    if stage is None:
        raise RuntimeError(f"Stage {name} is missing for job {job_id}")
    return stage


def _set_running(session: Session, job_id: str, name: str) -> None:
    stage = _stage(session, job_id, name)
    stage.status = "running"
    stage.started_at = utcnow()
    stage.error = None
    session.commit()
    logger.info("stage started", extra={"job_id": job_id, "stage": name})


def _set_succeeded(session: Session, job_id: str, name: str) -> None:
    stage = _stage(session, job_id, name)
    stage.status = "succeeded"
    stage.finished_at = utcnow()
    session.commit()
    logger.info("stage succeeded", extra={"job_id": job_id, "stage": name})


def _set_failed(session: Session, job_id: str, name: str, exc: Exception) -> None:
    session.rollback()
    message = str(exc)[:_ERROR_LIMIT] or exc.__class__.__name__
    stage = _stage(session, job_id, name)
    stage.status = "failed"
    stage.error = message
    stage.finished_at = utcnow()
    job = session.get(Job, job_id)
    if job is not None:
        job.status = "failed"
        job.error = message
        job.finished_at = utcnow()
    session.commit()
    logger.exception("stage failed", extra={"job_id": job_id, "stage": name})
