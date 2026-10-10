"""Claim queued discharge checks and run the workflow.

A background thread refreshes heartbeat_at about every 5 seconds. Recovery
treats a running job as abandoned when that timestamp is older than 45 seconds.
On startup, jobs left running by a previous process are queued again.
"""

import logging
import threading
import time

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.logging_config import configure_logging
from app.migrate import upgrade_db
from app.models import Job, JobStage, Medication
from app.workflow.graph import build_graph
from app.workflow.recovery import fail_running_job
from app.workflow.stage_status import utcnow
from app.workflow.tracing import configure_tracing

logger = logging.getLogger("app.worker")
POLL_SECONDS = 0.5
HEARTBEAT_SECONDS = 5


def claim_job(session: Session) -> Job | None:
    # Another worker may be claiming a job at the same time, so skip rows it has locked.
    job = session.scalar(
        select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1).with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    now = utcnow()
    job.status = "running"
    job.started_at = now
    job.heartbeat_at = now
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
        .values(
            status="queued",
            error=None,
            summary=None,
            critical_points=None,
            started_at=None,
            heartbeat_at=None,
            finished_at=None,
        )
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
    stop = threading.Event()
    beater = threading.Thread(target=_heartbeat, args=(job_id, stop), name=f"heartbeat-{job_id}", daemon=True)
    beater.start()
    try:
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            logger.info("job started", extra={"job_id": job_id, "stage": "parsed"})
            graph = build_graph(session)
            _invoke_graph(graph, job_id)
            logger.info("job finished", extra={"job_id": job_id, "stage": "done"})
    finally:
        stop.set()


def _heartbeat(job_id: str, stop: threading.Event) -> None:
    # While this timestamp stays fresh, the job stays running. After 45 quiet seconds, a status read fails it.
    while not stop.wait(HEARTBEAT_SECONDS):
        try:
            with SessionLocal() as session:
                job = session.get(Job, job_id)
                if job is None or job.status != "running":
                    return
                job.heartbeat_at = utcnow()
                session.commit()
        except Exception:
            logger.exception("heartbeat failed", extra={"job_id": job_id, "stage": "done"})


def _invoke_graph(graph, job_id: str) -> None:
    config = {
        "run_name": "formulary_verification",
        "metadata": {"job_id": job_id},
        "tags": ["formulary-check"],
    }
    if not configure_tracing():
        graph.invoke({"job_id": job_id}, config)
        return
    from langsmith.run_helpers import tracing_context

    with tracing_context(metadata={"job_id": job_id}, tags=["formulary-check"]):
        graph.invoke({"job_id": job_id}, config)


def main() -> None:
    configure_logging()
    configure_tracing()
    upgrade_db()
    with SessionLocal() as session:
        requeue_orphaned(session)
    while True:
        # Take the oldest queued job, run every stage, then look for the next one.
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
            with SessionLocal() as session:
                fail_running_job(session, job_id, "Verification stopped unexpectedly.")


if __name__ == "__main__":
    main()
