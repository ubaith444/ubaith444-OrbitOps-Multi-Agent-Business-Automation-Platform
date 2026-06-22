"""Add AI operations, prompt, evaluation, feedback, and playground records."""

from alembic import op

from app.models import (
    AgentEvaluation,
    AgentExecutionTrace,
    AgentFeedback,
    ModelRoute,
    PlaygroundRun,
    PromptVersion,
)

revision = "0005_ai_operations"
down_revision = "0004_communication_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    PromptVersion.__table__.create(bind=bind, checkfirst=True)
    ModelRoute.__table__.create(bind=bind, checkfirst=True)
    AgentExecutionTrace.__table__.create(bind=bind, checkfirst=True)
    AgentEvaluation.__table__.create(bind=bind, checkfirst=True)
    AgentFeedback.__table__.create(bind=bind, checkfirst=True)
    PlaygroundRun.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    PlaygroundRun.__table__.drop(bind=bind, checkfirst=True)
    AgentFeedback.__table__.drop(bind=bind, checkfirst=True)
    AgentEvaluation.__table__.drop(bind=bind, checkfirst=True)
    AgentExecutionTrace.__table__.drop(bind=bind, checkfirst=True)
    ModelRoute.__table__.drop(bind=bind, checkfirst=True)
    PromptVersion.__table__.drop(bind=bind, checkfirst=True)
