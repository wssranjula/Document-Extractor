"""List formularies and accept a new DOCX formulary.

The file is stored only when it contains Heading 2 drug monographs.
A rejected upload deletes the saved file.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.documents.formulary import chunk_reference
from app.models import Reference, User
from app.schemas import ReferenceOut
from app.storage import MAX_UPLOAD_BYTES, delete_file, save_upload

router = APIRouter()


def to_reference_out(reference: Reference) -> ReferenceOut:
    return ReferenceOut(
        id=reference.id,
        name=reference.name,
        filename=reference.filename,
        indexed=reference.indexed_at is not None,
    )


@router.get("", response_model=list[ReferenceOut])
def list_references(
    _: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[ReferenceOut]:
    rows = session.scalars(select(Reference).order_by(Reference.name)).all()
    return [to_reference_out(row) for row in rows]


@router.post("", response_model=ReferenceOut, status_code=201)
def create_reference(
    name: str = Form(..., min_length=1, max_length=255),
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ReferenceOut:
    reference = save_formulary(session, name, file)
    return to_reference_out(reference)


def save_formulary(session: Session, name: str, file: UploadFile) -> Reference:
    clean_name = " ".join(name.split())
    if not clean_name:
        raise HTTPException(status_code=422, detail="Enter a formulary name")
    if not file.filename or Path(file.filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=422, detail="Upload a DOCX formulary")
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="The file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="The file is larger than 20 MB")

    reference = Reference(
        name=clean_name,
        filename=Path(file.filename).name,
        storage_path="",
    )
    path = None
    try:
        session.add(reference)
        session.flush()
        path = save_upload(reference.id, reference.filename, content)
        reference.storage_path = str(path)
        if not chunk_reference(path):
            raise HTTPException(
                status_code=422,
                detail="The DOCX must contain drug monographs using Heading 2",
            )
        session.commit()
        session.refresh(reference)
    except HTTPException:
        session.rollback()
        if path is not None:
            delete_file(path)
        raise
    except Exception as exc:
        session.rollback()
        if path is not None:
            delete_file(path)
        raise HTTPException(status_code=422, detail="The DOCX could not be read") from exc
    return reference
