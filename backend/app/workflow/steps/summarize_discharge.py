"""Stage `summarized`: write one plain-language overview onto the job."""

import logging

from sqlalchemy.orm import Session

from app.documents.discharge import format_pages
from app.llm import SummaryResult, structured_completion
from app.models import Job
from app.workflow.prompts import SUMMARY_SYSTEM
from app.workflow.stage_status import run_stage

logger = logging.getLogger("app.workflow")


def summarize_discharge(session: Session):
    def stage(state: dict) -> dict:
        def work() -> dict:
            result = structured_completion(SUMMARY_SYSTEM, format_pages(state["pages"]), SummaryResult)
            job = session.get(Job, state["job_id"])
            job.summary = result.summary.strip()
            session.commit()
            logger.info("summarized document", extra={"job_id": state["job_id"], "stage": "summarized"})
            return {}

        return run_stage(session, state["job_id"], "summarized", work)

    return stage
