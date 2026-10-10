"""Split a formulary Word file into one chunk per drug.

Each Heading 2 is a drug monograph. The quick-reference section is kept as
its own chunk. Other headings are only titles, so they are not stored.
"""

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


def chunk_reference(path: Path) -> list[dict]:
    """Split a formulary into one chunk per drug monograph.

    Heading 2 is a monograph (Velantine, Cordizem-XR, and the rest).
    The quick-reference section is kept as its own chunk. Other Heading 1
    text is section framing and is not embedded.
    """
    document = Document(str(path))
    chunks: list[dict] = []
    title: str | None = None
    lines: list[str] = []
    page_number = 1
    start_page = 1

    def flush() -> None:
        if title and lines:
            chunks.append(
                {
                    "section": title,
                    "page": start_page,
                    "content": title + "\n" + "\n".join(lines),
                }
            )

    for paragraph in document.paragraphs:
        page_number += _page_breaks(paragraph)
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style is not None else ""
        if not text:
            continue
        if _is_monograph(style) or _is_quick_reference(style, text):
            flush()
            title = text
            lines = []
            start_page = page_number
            continue
        if style.startswith("Heading"):
            flush()
            title = None
            lines = []
            continue
        if title:
            lines.append(text)
    flush()
    return chunks


def _is_monograph(style: str) -> bool:
    return style in {"Heading 2", "Heading2"}


def _is_quick_reference(style: str, text: str) -> bool:
    return style in {"Heading 1", "Heading1"} and "Quick-Reference" in text


def _page_breaks(paragraph) -> int:
    count = 0
    for element in paragraph._element.iter():
        if element.tag == qn("w:lastRenderedPageBreak"):
            count += 1
        elif element.tag == qn("w:br") and element.get(qn("w:type")) == "page":
            count += 1
    return count
