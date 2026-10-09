import os
import shutil
from pathlib import Path

from sqlalchemy import select

from app.auth import hash_password
from app.config import REPO_ROOT, settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.migrate import upgrade_db
from app.models import Reference, User
from app.storage import upload_root

REFERENCE_NAME = "Meridian Bay Institutional Formulary"


def reference_source() -> Path:
    override = os.environ.get("SEED_REFERENCE_PATH")
    candidates = [
        Path(override) if override else None,
        REPO_ROOT / "reference_document_medical.docx",
        Path(__file__).resolve().parents[1] / "seed_data" / "reference_document_medical.docx",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    raise FileNotFoundError("reference_document_medical.docx was not found")


def seed() -> None:
    configure_logging()
    upgrade_db()
    source = reference_source()
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == settings.seed_email.lower()))
        if user is None:
            user = User(email=settings.seed_email.lower(), password_hash=hash_password(settings.seed_password))
            session.add(user)
        reference = session.scalar(select(Reference).where(Reference.name == REFERENCE_NAME))
        if reference is None:
            destination = upload_root() / "reference_document_medical.docx"
            shutil.copyfile(source, destination)
            reference = Reference(name=REFERENCE_NAME, filename=source.name, storage_path=str(destination))
            session.add(reference)
        session.commit()
        print(f"Reviewer login: {settings.seed_email} / {settings.seed_password}")
        print(f"Reference id: {reference.id}")


if __name__ == "__main__":
    seed()
