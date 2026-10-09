import logging
import time

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.logging_config import configure_logging
from app.migrate import upgrade_db
from app.models import Job, JobStage, Medication
from app.pipeline.graph import build_graph
from app.pipeline.stages import utcnow

logger = logging.getLogger("app.worker")
POLL_SECONDS = 0.5


def claim_job(session: Session) -> Job | None:
    job = session.scalar(
        select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1).with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = "running"
    job.started_at = utcnow()
    job.error = None
    session.commit()
    return job


def requeue_orphaned(session: Session) -> None:
    """A single worker restarts jobs that were left running by a previous process."""
    job_ids = list(session.scalars(select(Job.id).where(Job.status == "running")).all())
    if not job_ids:
        return
    session.execute(
        update(Job)
        .where(Job.id.in_(job_ids))
        .values(status="queued", error=None, summary=None, critical_points=None, started_at=None, finished_at=None)
    )
    session.execute(
        update(JobStage)
        .where(JobStage.job_id.in_(job_ids))
        .values(status="pending", error=None, started_at=None, finished_at=None)
    )
    session.execute(delete(Medication).where(Medication.job_id.in_(job_ids)))
    session.commit()
    logger.info("requeued %s interrupted job(s)", len(job_ids))


def run_job(job_id: str) -> None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        logger.info("job started", extra={"job_id": job_id, "stage": "parsed"})
        graph = build_graph(session)
        graph.invoke({"job_id": job_id})
        logger.info("job finished", extra={"job_id": job_id, "stage": "done"})


def main() -> None:
    configure_logging()
    upgrade_db()
    with SessionLocal() as session:
        requeue_orphaned(session)
    while True:
        with SessionLocal() as session:
            job = claim_job(session)
            job_id = job.id if job is not None else None
        if job_id is None:
            time.sleep(POLL_SECONDS)
            continue
        try:
            run_job(job_id)
        except Exception:
            logger.exception("job failed", extra={"job_id": job_id, "stage": "done"})


if __name__ == "__main__":
    main()
