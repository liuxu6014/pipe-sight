"""Scope templates to an owning user; backfill legacy rows to the first account."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op

revision = '20261114_template_user_scope'
down_revision = '20261110_auditor_role'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    user_id_comment = COLUMN_COMMENTS['templates']['user_id']
    op.add_column('templates', sa.Column('user_id', sa.BigInteger(), nullable=True, comment=user_id_comment))
    op.execute('UPDATE templates SET user_id = (SELECT id FROM sys_user ORDER BY id LIMIT 1) WHERE user_id IS NULL')
    op.alter_column('templates', 'user_id', nullable=False)
    op.create_foreign_key('fk_templates_user_id', 'templates', 'sys_user', ['user_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; downgrading would discard per-user template ownership.')
