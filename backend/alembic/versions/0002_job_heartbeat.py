"""Track worker heartbeats so a dead worker cannot leave a job running."""

from alembic import op
import sqlalchemy as sa

revision = "0002_job_heartbeat"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "heartbeat_at")
