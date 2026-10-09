import logging
import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Medication
from app.pipeline.llm import embed_texts, search_passages
from app.pipeline.verify import Passage

logger = logging.getLogger("app.pipeline")


def passages_for_medication(session: Session, reference_id: str, medication: Medication) -> list[Passage]:
    """Use the monograph whose title matches the drug name.

    Vector search runs only when no monograph title matches, so a similar
    drug cannot outrank the exact one.
    """
    named = _passages_by_name(session, reference_id, medication.drug_name)
    if named:
        logger.info("matched monograph by name", extra={"stage": "verified"})
        return named
    logger.info("no monograph title match; using vector search", extra={"stage": "verified"})
    query = " ".join(
        part
        for part in (
            medication.drug_name,
            medication.dose,
            medication.unit,
            medication.route,
            medication.frequency,
            medication.duration,
            medication.indication,
        )
        if part
    )
    vector = embed_texts([query])[0]
    return search_passages(session, reference_id, vector)


def _passages_by_name(session: Session, reference_id: str, drug_name: str) -> list[Passage]:
    target = normalize_name(drug_name)
    if not target:
        return []
    chunks = list(session.scalars(select(Chunk).where(Chunk.reference_id == reference_id)).all())
    monographs = [chunk for chunk in chunks if "quick-reference" not in chunk.section.lower()]
    exact = [chunk for chunk in monographs if normalize_name(chunk.section) == target]
    if exact:
        return [_passage(chunk) for chunk in exact]
    close = [
        chunk
        for chunk in monographs
        if _names_are_close(target, normalize_name(chunk.section))
    ]
    if len(close) == 1:
        return [_passage(close[0])]
    return []


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _names_are_close(left: str, right: str) -> bool:
    if len(left) < 5 or len(right) < 5:
        return False
    if left in right or right in left:
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.9


def _passage(chunk: Chunk) -> Passage:
    return Passage(section=chunk.section, page=chunk.page, content=chunk.content)
