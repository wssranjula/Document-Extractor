from app.db import SessionLocal
from app.models import Chunk, Medication, Reference
from app.pipeline.retrieve import passages_for_medication


def _reference_with_monographs() -> tuple[str, str]:
    with SessionLocal() as session:
        reference = Reference(name="Formulary", filename="reference.docx", storage_path="reference.docx")
        session.add(reference)
        session.flush()
        session.add_all(
            [
                Chunk(reference_id=reference.id, section="Velantine", page=1, content="Velantine\nMaximum dose: 40 mg."),
                Chunk(reference_id=reference.id, section="Cordizem-XR", page=2, content="Cordizem-XR\nStandard adult dose: 50 mg."),
                Chunk(
                    reference_id=reference.id,
                    section="VII. Quick-Reference Summary",
                    page=3,
                    content="Velantine 10 mg PO daily.",
                ),
            ]
        )
        medication = Medication(job_id="unused", drug_name="Cordizem XR", dose="50", unit="mg")
        session.add(medication)
        session.commit()
        return reference.id, medication.id


def test_punctuation_variant_uses_the_named_monograph_without_vectors(client, monkeypatch):
    def fail_embed(_texts):
        raise AssertionError("vector search should not run for a title match")

    monkeypatch.setattr("app.pipeline.retrieve.embed_texts", fail_embed)
    reference_id, medication_id = _reference_with_monographs()
    with SessionLocal() as session:
        medication = session.get(Medication, medication_id)
        passages = passages_for_medication(session, reference_id, medication)

    assert [passage.section for passage in passages] == ["Cordizem-XR"]


def test_unknown_name_falls_back_to_vector_search(client, monkeypatch):
    monkeypatch.setattr("app.pipeline.retrieve.embed_texts", lambda _texts: [[0.1, 0.2]])
    monkeypatch.setattr(
        "app.pipeline.retrieve.search_passages",
        lambda _session, _reference_id, _vector: [],
    )
    reference_id, medication_id = _reference_with_monographs()
    with SessionLocal() as session:
        medication = session.get(Medication, medication_id)
        medication.drug_name = "NotAFormularyDrug"
        passages = passages_for_medication(session, reference_id, medication)

    assert passages == []
