import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

ROUTES = {"po", "iv", "im", "sc", "sq", "pr", "sl", "topical", "oral", "inh"}


def read_document(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    raise ValueError("Only PDF and DOCX documents can be read")


def medications_in_tables(path: Path) -> list[dict]:
    """Read a discharge medication table when the document has one.

    The sample discharge list is a table, not body text. Reading those cells
    keeps the dose, route, and frequency that a paragraph parser would drop.
    """
    if path.suffix.lower() != ".docx":
        return []
    document = Document(str(path))
    page_number = 1
    medications = []
    for block in _blocks(document):
        if isinstance(block, Paragraph):
            page_number += _page_breaks(block)
            continue
        medications.extend(_medications_from_table(block, page_number))
    return medications


def _read_pdf(path: Path) -> list[dict]:
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        pages.append({"number": index, "text": page.extract_text() or ""})
    return pages


def _read_docx(path: Path) -> list[dict]:
    document = Document(str(path))
    pages: dict[int, list[str]] = {}
    page_number = 1
    for block in _blocks(document):
        if isinstance(block, Paragraph):
            page_number += _page_breaks(block)
            text = block.text.strip()
        else:
            text = _table_text(block)
        if text:
            pages.setdefault(page_number, []).append(text)
    if not pages:
        return [{"number": 1, "text": ""}]
    return [{"number": number, "text": "\n".join(lines)} for number, lines in sorted(pages.items())]


def _blocks(document):
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _table_text(table: Table) -> str:
    return "\n".join(" | ".join(row) for row in _table_rows(table))


def _table_rows(table: Table) -> list[list[str]]:
    rows = []
    for row in table.rows:
        cells = []
        seen = set()
        for cell in row.cells:
            identity = id(cell._tc)
            if identity in seen:
                continue
            seen.add(identity)
            cells.append(" ".join(cell.text.split()))
        if any(cells):
            rows.append(cells)
    return rows


def _medications_from_table(table: Table, page_number: int) -> list[dict]:
    rows = _table_rows(table)
    if len(rows) < 2:
        return []
    header = [cell.lower() for cell in rows[0]]
    name_at = _column(header, "medication", "drug")
    dose_at = _column(header, "dose")
    route_at = _column(header, "route", "frequency")
    if name_at is None or dose_at is None:
        return []
    duration_at = _column(header, "duration")
    indication_at = _column(header, "indication")
    medications = []
    for row in rows[1:]:
        drug_name = _cell(row, name_at)
        if not drug_name:
            continue
        dose, unit = _split_dose(_cell(row, dose_at))
        route, frequency = _split_route_frequency(_cell(row, route_at))
        medications.append(
            {
                "drug_name": drug_name,
                "dose": dose,
                "unit": unit,
                "route": route,
                "frequency": frequency,
                "duration": _cell(row, duration_at),
                "indication": _cell(row, indication_at),
                "source_page": page_number,
            }
        )
    return medications


def _column(header: list[str], *needles: str) -> int | None:
    for index, cell in enumerate(header):
        if any(needle in cell for needle in needles):
            return index
    return None


def _cell(row: list[str], index: int | None) -> str | None:
    if index is None or index >= len(row):
        return None
    value = row[index].strip()
    return value or None


def _split_dose(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([A-Za-zμµ%]+)?", value.strip())
    if not match:
        return value.strip(), None
    return match.group(1), match.group(2)


def _split_route_frequency(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    parts = value.strip().split(" ", 1)
    first = parts[0].rstrip(".,").lower()
    if first in ROUTES:
        frequency = parts[1].strip() if len(parts) > 1 else None
        return parts[0].rstrip(".,"), frequency or None
    return None, value.strip()


def _page_breaks(paragraph) -> int:
    count = 0
    for element in paragraph._element.iter():
        if element.tag == qn("w:lastRenderedPageBreak"):
            count += 1
        elif element.tag == qn("w:br") and element.get(qn("w:type")) == "page":
            count += 1
    return count


def format_pages(pages: list[dict]) -> str:
    return "\n\n".join(f"[page {page['number']}]\n{page['text']}" for page in pages)
