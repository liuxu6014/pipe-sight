"""Allow external reprocessing to be recorded in the content audit trail."""

from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_content_reprocess_audit'
down_revision = '20261002_content_review_workflow'
branch_labels = None
depends_on = None

TABLE = 'pipeline_content_review_events'
CONSTRAINT = 'ck_pipeline_review_event_action'


def upgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint(CONSTRAINT, TABLE, type_='check')
        op.create_check_constraint(
            CONSTRAINT,
            TABLE,
            "action IN ('approve', 'reject', 'withdraw', 'reprocess')",
        )
        return

    if TABLE not in set(inspect(op.get_bind()).get_table_names()):
        return
    op.drop_constraint(CONSTRAINT, TABLE, type_='check')
    op.create_check_constraint(
        CONSTRAINT,
        TABLE,
        "action IN ('approve', 'reject', 'withdraw', 'reprocess')",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_='check')
    op.create_check_constraint(
        CONSTRAINT,
        TABLE,
        "action IN ('approve', 'reject', 'withdraw')",
    )
