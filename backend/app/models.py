import json
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db import Base

STAGE_NAMES = [
    "parsed",
    "chunked",
    "embedded",
    "summarized",
    "key_points",
    "entities",
    "verified",
    "done",
]


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Reference(Base):
    __tablename__ = "references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reference_id: Mapped[str] = mapped_column(ForeignKey("references.id"))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reference: Mapped[Reference] = relationship()


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    critical_points: Mapped[list | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship()
    stages: Mapped[list["JobStage"]] = relationship(order_by="JobStage.position", cascade="all, delete-orphan")
    medications: Mapped[list["Medication"]] = relationship(cascade="all, delete-orphan")

    def critical_point_list(self) -> list:
        if not self.critical_points:
            return []
        return json.loads(self.critical_points)

    def set_critical_points(self, points: list) -> None:
        self.critical_points = json.dumps(points)


class JobStage(Base):
    __tablename__ = "job_stages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reference_id: Mapped[str] = mapped_column(ForeignKey("references.id"), index=True)
    section: Mapped[str] = mapped_column(String(255))
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(
        Vector(settings.embedding_dimensions).with_variant(Text(), "sqlite"),
        nullable=True,
    )


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    drug_name: Mapped[str] = mapped_column(String(255))
    dose: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route: Mapped[str | None] = mapped_column(String(64), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(128), nullable=True)
    indication: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    flag: Mapped["Flag | None"] = relationship(back_populates="medication", uselist=False, cascade="all, delete-orphan")


class Flag(Base):
    __tablename__ = "flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    medication_id: Mapped[str] = mapped_column(ForeignKey("medications.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(32))
    explanation: Mapped[str] = mapped_column(Text)
    citation_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    citation_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    medication: Mapped[Medication] = relationship(back_populates="flag")
