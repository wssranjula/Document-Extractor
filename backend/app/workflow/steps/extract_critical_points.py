"""Stage `key_points`: keep critical points whose quote appears in the discharge.

A point is dropped when its quote is not in the parsed pages, so the list
cannot add advice the document did not state.
"""

import logging

from sqlalchemy.orm import Session

from app.documents.discharge import format_pages
from app.llm import CriticalPointsResult, structured_completion
from app.models import Job
from app.workflow.prompts import POINTS_SYSTEM
from app.workflow.stage_status import run_stage

logger = logging.getLogger("app.workflow")


def extract_critical_points(session: Session):
    def stage(state: dict) -> dict:
        def work() -> dict:
            result = structured_completion(POINTS_SYSTEM, format_pages(state["pages"]), CriticalPointsResult)
            kept = _grounded_points(result, state["pages"])
            job = session.get(Job, state["job_id"])
            job.set_critical_points(kept)
            session.commit()
            logger.info("extracted key points", extra={"job_id": state["job_id"], "stage": "key_points"})
            return {}

        return run_stage(session, state["job_id"], "key_points", work)

    return stage


def _grounded_points(result: CriticalPointsResult, pages: list[dict]) -> list[dict]:
    source = " ".join(page["text"] for page in pages)
    normalized_source = " ".join(source.split()).lower()
    kept = []
    for point in result.points:
        quote = " ".join(point.source_quote.split())
        if not quote or quote.lower() not in normalized_source:
            logger.info("dropped ungrounded critical point")
            continue
        kept.append({"text": point.text.strip(), "source_page": point.source_page, "source_quote": quote})
    return kept
