from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Reference, User
from app.schemas import ReferenceOut

router = APIRouter()


@router.get("", response_model=list[ReferenceOut])
def list_references(
    _: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[ReferenceOut]:
    rows = session.scalars(select(Reference).order_by(Reference.name)).all()
    return [
        ReferenceOut(id=row.id, name=row.name, filename=row.filename, indexed=row.indexed_at is not None)
        for row in rows
    ]
