from pathlib import Path

from app.config import settings

ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def upload_root() -> Path:
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(document_id: str, filename: str, content: bytes) -> Path:
    suffix = Path(filename).suffix.lower()
    destination = upload_root() / f"{document_id}{suffix}"
    destination.write_bytes(content)
    return destination


def delete_file(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)
