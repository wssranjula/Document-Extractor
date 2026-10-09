import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Chunk, Flag, Job, Medication, Reference
from app.pipeline.chunking import chunk_reference
from app.pipeline.llm import (
    CriticalPointsResult,
    MedicationResult,
    MedicationsResult,
    SummaryResult,
    VerdictResult,
    complete,
    embed_texts,
)
from app.pipeline.parse import format_pages, medications_in_tables, read_document
from app.pipeline.retrieve import passages_for_medication
from app.pipeline.stages import run_stage, utcnow
from app.pipeline.verify import FlagDecision, Passage, verify_one

logger = logging.getLogger("app.pipeline")

SUMMARY_SYSTEM = (
    "You summarize a hospital discharge document for a clinician. "
    "Describe only what the document says. Do not add clinical advice, warnings, or facts that are not in the document. "
    "Write one faithful overview in plain prose."
)
POINTS_SYSTEM = (
    "Extract critical points a patient must not miss from this discharge document. "
    "Examples are a required dose time, a duration limit, a side effect to report, or a follow-up. "
    "Every point must quote a phrase that appears in the document. Do not invent recommendations. "
    "Order the list with the most important point first."
)
ENTITY_SYSTEM = (
    "Extract every prescribed medication from this discharge document. "
    "Medication lists are often tables. Read every table column, not only the surrounding paragraphs. "
    "Return drug name, dose, unit, route, frequency, duration, indication, and the source page number. "
    "Split a combined route and frequency such as 'PO once daily' into route PO and frequency once daily. "
    "Use null for any field the document does not state. Do not infer medications that are not prescribed."
)
VERIFY_SYSTEM = (
    "You verify one prescription against the institutional formulary passages provided. "
    "The prescription fields below are the extracted values. Compare those values. "
    "Never describe a field as missing when it contains a value. "
    "supported means a monograph exists and the stated dose, route, frequency, timing, and duration agree with it. "
    "A dose equal to the standard adult dose is supported. "
    "A dose above the stated maximum is contradicted. "
    "A dose other than the standard adult dose is contradicted unless the prescription documents a titration the monograph allows. "
    "An administration time the monograph forbids, such as morning instead of bedtime, is contradicted. "
    "A duration longer than the monograph allows is contradicted. "
    "A duration that matches a required reassessment point is supported. "
    "contradicted means a monograph exists but at least one stated parameter conflicts. "
    "unsupported means the passages do not contain a monograph for this medication. "
    "citation_quote must be copied from one passage. Do not use knowledge from outside the passages."
)


def build_nodes(session: Session):
    def parsed(state: dict) -> dict:
        def work() -> dict:
            document = session.get(Job, state["job_id"]).document
            pages = read_document(Path(document.storage_path))
            if not any(page["text"].strip() for page in pages):
                raise ValueError("The document has no readable text")
            logger.info("parsed document", extra={"job_id": state["job_id"], "stage": "parsed"})
            return {"pages": pages}

        return run_stage(session, state["job_id"], "parsed", work)

    def chunked(state: dict) -> dict:
        def work() -> dict:
            reference = _reference(session, state)
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
            logger.info(
                "chunked reference",
                extra={"job_id": state["job_id"], "stage": "chunked"},
            )
            return {}

        return run_stage(session, state["job_id"], "chunked", work)

    def embedded(state: dict) -> dict:
        def work() -> dict:
            reference = _reference(session, state)
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

    def summarized(state: dict) -> dict:
        def work() -> dict:
            result = complete(SUMMARY_SYSTEM, format_pages(state["pages"]), SummaryResult)
            job = session.get(Job, state["job_id"])
            job.summary = result.summary.strip()
            session.commit()
            logger.info("summarized document", extra={"job_id": state["job_id"], "stage": "summarized"})
            return {}

        return run_stage(session, state["job_id"], "summarized", work)

    def key_points(state: dict) -> dict:
        def work() -> dict:
            result = complete(POINTS_SYSTEM, format_pages(state["pages"]), CriticalPointsResult)
            kept = _grounded_points(result, state["pages"])
            job = session.get(Job, state["job_id"])
            job.set_critical_points(kept)
            session.commit()
            logger.info("extracted key points", extra={"job_id": state["job_id"], "stage": "key_points"})
            return {}

        return run_stage(session, state["job_id"], "key_points", work)

    def entities(state: dict) -> dict:
        def work() -> dict:
            document = session.get(Job, state["job_id"]).document
            table_rows = medications_in_tables(Path(document.storage_path))
            if table_rows:
                extracted = [MedicationResult(**row) for row in table_rows]
                logger.info("extracted medications from table", extra={"job_id": state["job_id"], "stage": "entities"})
            else:
                extracted = complete(ENTITY_SYSTEM, format_pages(state["pages"]), MedicationsResult).medications
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

    def verified(state: dict) -> dict:
        def work() -> dict:
            job = session.get(Job, state["job_id"])
            reference_id = job.document.reference_id
            medications = list(session.scalars(select(Medication).where(Medication.job_id == job.id)).all())
            for medication in medications:
                passages = _passages_for(session, reference_id, medication)
                verdict = _ask_verdict(medication, passages)
                decision = verify_one(passages, verdict)
                _replace_flag(session, medication, decision)
            session.commit()
            logger.info("verified medications", extra={"job_id": state["job_id"], "stage": "verified"})
            return {}

        return run_stage(session, state["job_id"], "verified", work)

    def done(state: dict) -> dict:
        def work() -> dict:
            job = session.get(Job, state["job_id"])
            job.status = "succeeded"
            job.error = None
            job.finished_at = utcnow()
            session.commit()
            logger.info("job finished", extra={"job_id": state["job_id"], "stage": "done"})
            return {}

        return run_stage(session, state["job_id"], "done", work)

    return {
        "parsed": parsed,
        "chunked": chunked,
        "embedded": embedded,
        "summarized": summarized,
        "key_points": key_points,
        "entities": entities,
        "verified": verified,
        "done": done,
    }


def _reference(session: Session, state: dict) -> Reference:
    job = session.get(Job, state["job_id"])
    reference = session.get(Reference, job.document.reference_id)
    if reference is None:
        raise ValueError("The selected reference document does not exist")
    return reference


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


def _passages_for(session: Session, reference_id: str, medication: Medication) -> list[Passage]:
    return passages_for_medication(session, reference_id, medication)


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
    result = complete(
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


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
