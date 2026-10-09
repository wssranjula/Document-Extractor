from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from pypdf import PdfReader


def read_document(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    raise ValueError("Only PDF and DOCX documents can be read")


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
    for paragraph in document.paragraphs:
        page_number += _page_breaks(paragraph)
        text = paragraph.text.strip()
        if text:
            pages.setdefault(page_number, []).append(text)
    if not pages:
        return [{"number": 1, "text": ""}]
    return [{"number": number, "text": "\n".join(lines)} for number, lines in sorted(pages.items())]


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
