"""Stage `parsed`: read the discharge PDF or DOCX into page text.

The pages stay in the graph state for the later summary and medication steps.
This stage does not write the document text to the database.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.documents.discharge import read_document
from app.models import Job
from app.workflow.stage_status import run_stage

logger = logging.getLogger("app.workflow")


def parse_discharge(session: Session):
    def stage(state: dict) -> dict:
        def work() -> dict:
            document = session.get(Job, state["job_id"]).document
            pages = read_document(Path(document.storage_path))
            if not any(page["text"].strip() for page in pages):
                raise ValueError("The document has no readable text")
            logger.info("parsed document", extra={"job_id": state["job_id"], "stage": "parsed"})
            return {"pages": pages}

        return run_stage(session, state["job_id"], "parsed", work)

    return stage
