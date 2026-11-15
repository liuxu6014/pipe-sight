"""Index the owner column of digest schedules for user-scoped listing."""

from alembic import op

revision = '20261115_digest_schedule_user_index'
down_revision = '20261115_template_schedule_contract'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('idx_digest_schedules_user_id', 'digest_schedules', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_digest_schedules_user_id', table_name='digest_schedules')
