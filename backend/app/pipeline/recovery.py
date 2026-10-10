import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Job
from app.pipeline.stages import utcnow

logger = logging.getLogger("app.pipeline")

STALE_AFTER = timedelta(seconds=45)
STALE_ERROR = "The worker stopped before this check finished. Submit the document again."


def fail_stale_jobs(session: Session, *, now: datetime | None = None) -> list[str]:
    """Fail running jobs whose worker has stopped reporting.

    The API calls this while reading jobs, so a crashed worker is visible
    without waiting for the next worker process to start.
    """
    moment = now or utcnow()
    cutoff = moment - STALE_AFTER
    jobs = session.scalars(
        select(Job).where(Job.status == "running").options(selectinload(Job.stages))
    ).all()
    failed_ids = []
    for job in jobs:
        last_seen = _aware(job.heartbeat_at) or _aware(job.started_at)
        if last_seen is not None and last_seen >= cutoff:
            continue
        _mark_failed(job, STALE_ERROR, moment)
        failed_ids.append(job.id)
        logger.error("stale job failed", extra={"job_id": job.id, "stage": _running_stage_name(job)})
    if failed_ids:
        session.commit()
    return failed_ids


def fail_running_job(session: Session, job_id: str, message: str) -> None:
    job = session.scalar(select(Job).where(Job.id == job_id).options(selectinload(Job.stages)))
    if job is None or job.status != "running":
        return
    _mark_failed(job, message, utcnow())
    session.commit()
    logger.error("running job failed", extra={"job_id": job_id, "stage": _running_stage_name(job)})


def _mark_failed(job: Job, message: str, moment: datetime) -> None:
    job.status = "failed"
    job.error = message
    job.finished_at = moment
    for stage in sorted(job.stages, key=lambda item: item.position):
        if stage.status == "running":
            stage.status = "failed"
            stage.error = message
            stage.finished_at = moment
            return


def _running_stage_name(job: Job) -> str:
    for stage in sorted(job.stages, key=lambda item: item.position):
        if stage.status in {"running", "failed"}:
            return stage.name
    return "done"


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
