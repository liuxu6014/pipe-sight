"""Allow digest schedules to record an explicit holiday skip result."""

from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_digest_holiday_policy'
down_revision = '20261003_report_publications'
branch_labels = None
depends_on = None

TABLE_NAME = 'digest_schedules'
CONSTRAINT_NAME = 'ck_digest_schedules_last_status'


def upgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_='check')
        op.create_check_constraint(
            CONSTRAINT_NAME,
            TABLE_NAME,
            "last_status IS NULL OR last_status IN ('queued', 'no_data', 'skipped', 'failed')",
        )
        return
    inspector = inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return
    constraint_names = {item.get('name') for item in inspector.get_check_constraints(TABLE_NAME)}
    if CONSTRAINT_NAME in constraint_names:
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_='check')
    op.create_check_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        "last_status IS NULL OR last_status IN ('queued', 'no_data', 'skipped', 'failed')",
    )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_='check')
        op.create_check_constraint(
            CONSTRAINT_NAME,
            TABLE_NAME,
            "last_status IS NULL OR last_status IN ('queued', 'no_data', 'failed')",
        )
        return
    if TABLE_NAME not in inspect(op.get_bind()).get_table_names():
        return
    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_='check')
    op.create_check_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        "last_status IS NULL OR last_status IN ('queued', 'no_data', 'failed')",
    )
