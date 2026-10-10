"""Stage `embedded`: store a vector for each new formulary chunk.

Skipped when the formulary was indexed by an earlier job. The first job to
index a formulary sets indexed_at, which is the signal later jobs check.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import embed_texts
from app.models import Chunk
from app.workflow.job_context import reference_for_job
from app.workflow.stage_status import run_stage, utcnow

logger = logging.getLogger("app.workflow")


def embed_formulary(session: Session):
    def stage(state: dict) -> dict:
        def work() -> dict:
            reference = reference_for_job(session, state["job_id"])
            if reference.indexed_at is not None:
                logger.info("reference index hit", extra={"job_id": state["job_id"], "stage": "embedded"})
                return {}
            rows = list(
                session.scalars(
                    select(Chunk).where(Chunk.reference_id == reference.id, Chunk.embedding.is_(None))
                ).all()
            )
            vectors = embed_texts([row.content for row in rows])
            for row, vector in zip(rows, vectors, strict=True):
                row.embedding = vector
            reference.indexed_at = utcnow()
            session.commit()
            logger.info("embedded reference", extra={"job_id": state["job_id"], "stage": "embedded"})
            return {}

        return run_stage(session, state["job_id"], "embedded", work)

    return stage
