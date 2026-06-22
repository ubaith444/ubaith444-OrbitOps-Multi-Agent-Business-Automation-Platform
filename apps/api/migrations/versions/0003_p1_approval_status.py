"""Add the request-changes approval outcome."""

from alembic import op

revision = "0003_p1_approval_status"
down_revision = "0002_immutable_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE approvalstatus ADD VALUE IF NOT EXISTS 'CHANGES_REQUESTED'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely while rows may reference them.
    pass
