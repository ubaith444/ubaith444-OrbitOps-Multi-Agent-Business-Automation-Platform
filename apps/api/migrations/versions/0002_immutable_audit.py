"""Make audit logs append-only at the database boundary."""

from alembic import op
from sqlalchemy import inspect

from app.models import Report

revision = "0002_immutable_audit"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Report.__table__.create(bind=bind, checkfirst=True)
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'AGENT_VIEWER'")
    constraints = {item["name"] for item in inspect(bind).get_unique_constraints("approvals")}
    if "uq_approval_run_kind" not in constraints:
        op.create_unique_constraint("uq_approval_run_kind", "approvals", ["run_id", "kind"])
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
        RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'audit_logs are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    Report.__table__.drop(bind=op.get_bind(), checkfirst=True)
