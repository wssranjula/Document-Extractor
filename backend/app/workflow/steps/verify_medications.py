"""Stage `verified`: compare each extracted medication with the formulary.

The model sees only the passages retrieval returned. verification.py then
drops a verdict whose quote is not in those passages.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import VerdictResult, structured_completion
from app.models import Flag, Job, Medication
from app.retrieval import passages_for_medication
from app.verification import FlagDecision, Passage, remove_unsupported_duration_conflict, verify_one
from app.workflow.prompts import VERIFY_SYSTEM
from app.workflow.stage_status import run_stage

logger = logging.getLogger("app.workflow")


def verify_medications(session: Session):
    def stage(state: dict) -> dict:
        def work() -> dict:
            job = session.get(Job, state["job_id"])
            reference_id = job.document.reference_id
            medications = list(session.scalars(select(Medication).where(Medication.job_id == job.id)).all())
            for medication in medications:
                passages = passages_for_medication(session, reference_id, medication)
                verdict = _ask_verdict(medication, passages)
                if verdict is not None:
                    verdict = remove_unsupported_duration_conflict(medication.duration, passages, verdict)
                decision = verify_one(passages, verdict)
                _replace_flag(session, medication, decision)
            session.commit()
            logger.info("verified medications", extra={"job_id": state["job_id"], "stage": "verified"})
            return {}

        return run_stage(session, state["job_id"], "verified", work)

    return stage


def _ask_verdict(medication: Medication, passages: list[Passage]) -> FlagDecision | None:
    if not passages:
        return None
    passage_text = "\n\n".join(
        f"Section: {passage.section}\nPage: {passage.page}\n{passage.content}" for passage in passages
    )
    medication_text = (
        f"Drug: {medication.drug_name}\n"
        f"Dose: {_stated(medication.dose, medication.unit)}\n"
        f"Route: {_stated(medication.route)}\n"
        f"Frequency: {_stated(medication.frequency)}\n"
        f"Duration: {_stated(medication.duration)}\n"
        f"Indication: {_stated(medication.indication)}"
    )
    result = structured_completion(
        VERIFY_SYSTEM,
        f"Prescription:\n{medication_text}\n\nFormulary passages:\n{passage_text}",
        VerdictResult,
    )
    return FlagDecision(
        status=result.status.strip().lower(),
        explanation=result.explanation.strip(),
        citation_quote=result.citation_quote,
        citation_section=result.citation_section,
        citation_page=result.citation_page,
    )


def _replace_flag(session: Session, medication: Medication, decision: FlagDecision) -> None:
    if medication.flag is not None:
        session.delete(medication.flag)
        session.flush()
    session.add(
        Flag(
            medication_id=medication.id,
            status=decision.status,
            explanation=decision.explanation,
            citation_quote=decision.citation_quote,
            citation_section=decision.citation_section,
            citation_page=decision.citation_page,
        )
    )


def _stated(*values: str | None) -> str:
    text = " ".join(value.strip() for value in values if value and value.strip())
    return text or "not stated"
