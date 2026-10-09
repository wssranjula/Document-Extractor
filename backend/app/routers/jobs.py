import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.db import SessionLocal, get_db
from app.models import STAGE_NAMES, Document, Job, JobStage, Medication, Reference, User
from app.schemas import (
    CitationOut,
    CriticalPointOut,
    FlagOut,
    JobCreated,
    JobOut,
    JobResult,
    MedicationOut,
    StageOut,
)
from app.storage import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, delete_file, save_upload

router = APIRouter()


def get_owned_job(session: Session, job_id: str, user_id: str) -> Job:
    job = session.scalar(
        select(Job)
        .where(Job.id == job_id, Job.user_id == user_id)
        .options(
            selectinload(Job.stages),
            selectinload(Job.medications).selectinload(Medication.flag),
            selectinload(Job.document),
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def to_job_out(job: Job) -> JobOut:
    stages = sorted(job.stages, key=lambda stage: stage.position)
    return JobOut(
        id=job.id,
        status=job.status,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        stages=[
            StageOut(
                name=stage.name,
                status=stage.status,
                started_at=stage.started_at,
                finished_at=stage.finished_at,
                error=stage.error,
            )
            for stage in stages
        ],
    )


@router.post("", response_model=JobCreated, status_code=201)
def create_job(
    reference_id: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> JobCreated:
    if not file.filename:
        raise HTTPException(status_code=422, detail="Upload a PDF or DOCX file")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail="Upload a PDF or DOCX file")
    reference = session.get(Reference, reference_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="The file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="The file is larger than 20 MB")

    document = Document(
        user_id=user.id,
        reference_id=reference.id,
        filename=Path(file.filename).name,
        content_type=ALLOWED_EXTENSIONS[suffix],
        storage_path="",
    )
    path = None
    try:
        session.add(document)
        session.flush()
        path = save_upload(document.id, document.filename, content)
        document.storage_path = str(path)
        job = Job(document_id=document.id, user_id=user.id, status="queued")
        session.add(job)
        session.flush()
        for position, name in enumerate(STAGE_NAMES):
            session.add(JobStage(job_id=job.id, name=name, position=position, status="pending"))
        session.commit()
    except Exception:
        session.rollback()
        if path is not None:
            delete_file(path)
        raise
    return JobCreated(job_id=job.id, status=job.status)


@router.get("", response_model=list[JobOut])
def list_jobs(user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> list[JobOut]:
    jobs = session.scalars(
        select(Job).where(Job.user_id == user.id).options(selectinload(Job.stages)).order_by(Job.created_at.desc())
    ).all()
    return [to_job_out(job) for job in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> JobOut:
    return to_job_out(get_owned_job(session, job_id, user.id))


@router.get("/{job_id}/events")
async def job_events(job_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_db)):
    get_owned_job(session, job_id, user.id)
    return StreamingResponse(
        _event_stream(job_id, user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}/result", response_model=JobResult)
def job_result(job_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> JobResult:
    job = get_owned_job(session, job_id, user.id)
    medications = []
    for medication in job.medications:
        flag = None
        if medication.flag is not None:
            citation = None
            if medication.flag.citation_quote:
                citation = CitationOut(
                    quote=medication.flag.citation_quote,
                    section=medication.flag.citation_section,
                    page=medication.flag.citation_page,
                )
            flag = FlagOut(status=medication.flag.status, explanation=medication.flag.explanation, citation=citation)
        medications.append(
            MedicationOut(
                id=medication.id,
                drug_name=medication.drug_name,
                dose=medication.dose,
                unit=medication.unit,
                route=medication.route,
                frequency=medication.frequency,
                duration=medication.duration,
                indication=medication.indication,
                source_page=medication.source_page,
                flag=flag,
            )
        )
    return JobResult(
        job_id=job.id,
        summary=job.summary,
        critical_points=[CriticalPointOut(**point) for point in job.critical_point_list()],
        medications=medications,
    )


@router.get("/{job_id}/file")
def job_file(job_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_db)):
    job = get_owned_job(session, job_id, user.id)
    path = Path(job.document.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Job not found")
    return FileResponse(path, media_type=job.document.content_type, filename=job.document.filename)


async def _event_stream(job_id: str, user_id: str):
    last_payload = None
    ticks = 0
    while True:
        with SessionLocal() as session:
            job = session.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id).options(selectinload(Job.stages)))
            if job is None:
                yield _sse("failed", {"job_id": job_id, "status": "failed"})
                return
            payload = {
                "job_id": job.id,
                "status": job.status,
                "stages": [
                    {
                        "name": stage.name,
                        "status": stage.status,
                        "started_at": _iso(stage.started_at),
                        "finished_at": _iso(stage.finished_at),
                        "error": stage.error,
                    }
                    for stage in sorted(job.stages, key=lambda item: item.position)
                ],
            }
            status = job.status
        encoded = json.dumps(payload)
        if encoded != last_payload:
            yield _sse("stage", payload)
            last_payload = encoded
        if status in {"succeeded", "failed"}:
            event = "done" if status == "succeeded" else "failed"
            yield _sse(event, {"job_id": job_id, "status": status})
            return
        ticks += 1
        if ticks % 25 == 0:
            yield ": keep-alive\n\n"
        await asyncio.sleep(0.4)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()
