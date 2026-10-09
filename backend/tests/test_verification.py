from sqlalchemy import select

from app.db import SessionLocal
from app.models import Document, Flag, Job, Medication, Reference, User
from app.pipeline.verify import FlagDecision, Passage, verify_one

QUOTE = "Maximum dose: 40 mg orally once daily."
PASSAGE = Passage(
    section="Velantine",
    page=1,
    content=(
        "Velantine\n"
        "Standard adult dose: 10 mg orally once daily.\n"
        f"{QUOTE}\n"
    ),
)


def _store(decision: FlagDecision) -> Flag:
    with SessionLocal() as session:
        user = User(email="verify@example.com", password_hash="hash")
        reference = Reference(name="Formulary", filename="reference.docx", storage_path="reference.docx")
        session.add_all([user, reference])
        session.flush()
        document = Document(
            user_id=user.id,
            reference_id=reference.id,
            filename="discharge.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            storage_path="discharge.docx",
        )
        session.add(document)
        session.flush()
        job = Job(document_id=document.id, user_id=user.id, status="running")
        session.add(job)
        session.flush()
        medication = Medication(
            job_id=job.id,
            drug_name="Velantine",
            dose="80",
            unit="mg",
            route="oral",
            frequency="once daily",
            source_page=1,
        )
        session.add(medication)
        session.flush()
        flag = Flag(
            medication_id=medication.id,
            status=decision.status,
            explanation=decision.explanation,
            citation_quote=decision.citation_quote,
            citation_section=decision.citation_section,
            citation_page=decision.citation_page,
        )
        session.add(flag)
        session.commit()
        flag_id = flag.id
    with SessionLocal() as session:
        return session.scalar(select(Flag).where(Flag.id == flag_id))


def test_contradicted_dose_is_stored_with_its_quote(client):
    verdict = FlagDecision(
        status="contradicted",
        explanation="80 mg exceeds the formulary maximum of 40 mg once daily.",
        citation_quote=QUOTE,
        citation_section="Velantine",
        citation_page=1,
    )
    decision = verify_one([PASSAGE], verdict)
    stored = _store(decision)

    assert stored.status == "contradicted"
    assert stored.citation_quote == QUOTE
    assert stored.citation_section == "Velantine"


def test_missing_passage_is_unsupported_without_a_citation(client):
    decision = verify_one([], verdict=None)
    stored = _store(decision)

    assert stored.status == "unsupported"
    assert stored.citation_quote is None
    assert stored.citation_section is None
    assert "no relevant formulary passage" in stored.explanation.lower()
