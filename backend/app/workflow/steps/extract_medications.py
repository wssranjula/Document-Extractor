"""Stage `entities`: store the prescribed medications from the discharge.

A Word medication table is read directly. A document without that table
asks the model instead. The stage id stays `entities` for existing jobs.
"""

import logging
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.documents.discharge import format_pages, medications_in_tables
from app.llm import MedicationResult, MedicationsResult, structured_completion
from app.models import Job, Medication
from app.workflow.prompts import ENTITY_SYSTEM
from app.workflow.stage_status import run_stage

logger = logging.getLogger("app.workflow")


def extract_medications(session: Session):
    def stage(state: dict) -> dict:
        def work() -> dict:
            document = session.get(Job, state["job_id"]).document
            table_rows = medications_in_tables(Path(document.storage_path))
            if table_rows:
                extracted = [MedicationResult(**row) for row in table_rows]
                logger.info("extracted medications from table", extra={"job_id": state["job_id"], "stage": "entities"})
            else:
                extracted = structured_completion(
                    ENTITY_SYSTEM, format_pages(state["pages"]), MedicationsResult
                ).medications
            job_id = state["job_id"]
            session.execute(delete(Medication).where(Medication.job_id == job_id))
            for item in extracted:
                if not item.drug_name.strip():
                    continue
                session.add(_medication(job_id, item))
            session.commit()
            logger.info("extracted medications", extra={"job_id": job_id, "stage": "entities"})
            return {}

        return run_stage(session, state["job_id"], "entities", work)

    return stage


def _medication(job_id: str, item: MedicationResult) -> Medication:
    return Medication(
        job_id=job_id,
        drug_name=item.drug_name.strip(),
        dose=_blank(item.dose),
        unit=_blank(item.unit),
        route=_blank(item.route),
        frequency=_blank(item.frequency),
        duration=_blank(item.duration),
        indication=_blank(item.indication),
        source_page=item.source_page,
    )


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
