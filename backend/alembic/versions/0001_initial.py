"""Initial schema."""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reference_id", sa.String(36), sa.ForeignKey("references.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, unique=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("critical_points", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "job_stages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_job_stages_job_id", "job_stages", ["job_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reference_id", sa.String(36), sa.ForeignKey("references.id"), nullable=False),
        sa.Column("section", sa.String(255), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_index("ix_chunks_reference_id", "chunks", ["reference_id"])
    op.execute(
        "CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "medications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("drug_name", sa.String(255), nullable=False),
        sa.Column("dose", sa.String(64), nullable=True),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("route", sa.String(64), nullable=True),
        sa.Column("frequency", sa.String(128), nullable=True),
        sa.Column("duration", sa.String(128), nullable=True),
        sa.Column("indication", sa.Text(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
    )
    op.create_index("ix_medications_job_id", "medications", ["job_id"])

    op.create_table(
        "flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("medication_id", sa.String(36), sa.ForeignKey("medications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("citation_quote", sa.Text(), nullable=True),
        sa.Column("citation_section", sa.String(255), nullable=True),
        sa.Column("citation_page", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("flags")
    op.drop_table("medications")
    op.drop_index("chunks_embedding_idx", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("job_stages")
    op.drop_table("jobs")
    op.drop_table("documents")
    op.drop_table("references")
    op.drop_table("users")
