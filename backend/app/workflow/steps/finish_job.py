"""Stage `done`: mark the job succeeded when it is still running.

A job that recovery already failed stays failed. This stage does not
overwrite that outcome.
"""

import logging

from sqlalchemy.orm import Session

from app.models import Job
from app.workflow.stage_status import run_stage, utcnow

logger = logging.getLogger("app.workflow")


def finish_job(session: Session):
    def stage(state: dict) -> dict:
        def work() -> dict:
            session.expire_all()
            job = session.get(Job, state["job_id"])
            if job is None or job.status != "running":
                return {}
            job.status = "succeeded"
            job.error = None
            job.finished_at = utcnow()
            session.commit()
            logger.info("job finished", extra={"job_id": state["job_id"], "stage": "done"})
            return {}

        return run_stage(session, state["job_id"], "done", work)

    return stage
