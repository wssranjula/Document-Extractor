from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ReferenceOut(BaseModel):
    id: str
    name: str
    filename: str
    indexed: bool


class StageOut(BaseModel):
    name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None


class JobOut(BaseModel):
    id: str
    status: str
    error: str | None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    stages: list[StageOut]


class JobCreated(BaseModel):
    job_id: str
    status: str


class CitationOut(BaseModel):
    quote: str | None
    section: str | None
    page: int | None


class FlagOut(BaseModel):
    status: str
    explanation: str
    citation: CitationOut | None


class MedicationOut(BaseModel):
    id: str
    drug_name: str
    dose: str | None
    unit: str | None
    route: str | None
    frequency: str | None
    duration: str | None
    indication: str | None
    source_page: int | None
    flag: FlagOut | None


class CriticalPointOut(BaseModel):
    text: str
    source_page: int | None
    source_quote: str


class JobResult(BaseModel):
    job_id: str
    summary: str | None
    critical_points: list[CriticalPointOut]
    medications: list[MedicationOut]
