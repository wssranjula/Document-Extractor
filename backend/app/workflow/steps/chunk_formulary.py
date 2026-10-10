"""Stage `chunked`: split the formulary into one chunk per monograph.

A formulary that already has indexed_at is left untouched. The stage still
succeeds, so a later discharge against the same formulary does not rebuild it.
"""

import logging
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.documents.formulary import chunk_reference
from app.models import Chunk
from app.workflow.job_context import reference_for_job
from app.workflow.stage_status import run_stage

logger = logging.getLogger("app.workflow")


def chunk_formulary(session: Session):
    def stage(state: dict) -> dict:
        def work() -> dict:
            reference = reference_for_job(session, state["job_id"])
            if reference.indexed_at is not None:
                logger.info("reference index hit", extra={"job_id": state["job_id"], "stage": "chunked"})
                return {}
            drafts = chunk_reference(Path(reference.storage_path))
            if not drafts:
                raise ValueError("The reference document has no monograph chunks")
            session.execute(delete(Chunk).where(Chunk.reference_id == reference.id))
            for draft in drafts:
                session.add(
                    Chunk(
                        reference_id=reference.id,
                        section=draft["section"],
                        page=draft["page"],
                        content=draft["content"],
                    )
                )
            session.commit()
            logger.info("chunked reference", extra={"job_id": state["job_id"], "stage": "chunked"})
            return {}

        return run_stage(session, state["job_id"], "chunked", work)

    return stage
