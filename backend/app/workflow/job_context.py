"""Load the formulary that was selected when a discharge was uploaded."""

from sqlalchemy.orm import Session

from app.models import Job, Reference


def reference_for_job(session: Session, job_id: str) -> Reference:
    job = session.get(Job, job_id)
    reference = session.get(Reference, job.document.reference_id)
    if reference is None:
        raise ValueError("The selected reference document does not exist")
    return reference
