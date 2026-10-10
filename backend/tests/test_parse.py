from app.config import REPO_ROOT
from app.documents.discharge import format_pages, medications_in_tables, read_document


def test_discharge_table_is_included_in_the_parsed_text():
    pages = read_document(REPO_ROOT / "primary_document_medical.docx")
    text = format_pages(pages)

    assert "Velantine | 10 mg | PO once daily | Continue indefinitely | Hypertension" in text
    assert "Cordizem-XR | 100 mg | PO once daily" in text
    assert "Pravoxil | 20 mg | PO every morning" in text


def test_discharge_table_keeps_dose_route_and_frequency():
    rows = {row["drug_name"]: row for row in medications_in_tables(REPO_ROOT / "primary_document_medical.docx")}

    assert rows["Velantine"]["dose"] == "10"
    assert rows["Velantine"]["unit"] == "mg"
    assert rows["Velantine"]["route"] == "PO"
    assert rows["Velantine"]["frequency"] == "once daily"
    assert rows["Cordizem-XR"]["dose"] == "100"
    assert rows["Cordizem-XR"]["frequency"] == "once daily"
    assert rows["Pravoxil"]["frequency"] == "every morning"
    assert rows["Etrazolam"]["dose"] == "0.5"
    assert rows["Etrazolam"]["frequency"] == "twice daily"
    assert rows["Etrazolam"]["duration"] == "8 weeks"
    assert rows["Quintaxin"]["frequency"] == "once daily, before breakfast"
    assert rows["Pranixol"]["dose"] == "10"
