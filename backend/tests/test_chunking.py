from app.config import REPO_ROOT
from app.pipeline.chunking import chunk_reference


def test_reference_chunks_follow_monographs():
    path = REPO_ROOT / "reference_document_medical.docx"
    chunks = chunk_reference(path)
    titles = [chunk["section"] for chunk in chunks]
    assert titles == [
        "Velantine",
        "Cordizem-XR",
        "Mirosartan",
        "Pravoxil",
        "Etrazolam",
        "Sumavast",
        "Quintaxin",
        "Floranase",
        "VII. Quick-Reference Summary",
    ]
    assert "Maximum dose: 40 mg orally once daily." in chunks[0]["content"]
