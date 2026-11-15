"""Stable personal defaults and recoverable template deletion; preserve existing rows."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = '20261115_template_defaults'
down_revision = '20261114_template_user_scope'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    comments = COLUMN_COMMENTS['templates']
    op.add_column('templates', sa.Column('preset_key', sa.String(64), nullable=True, comment=comments['preset_key']))
    op.add_column('templates', sa.Column('deleted_at', TIMESTAMP(precision=0), nullable=True, comment=comments['deleted_at']))
    op.create_unique_constraint('uq_templates_user_preset', 'templates', ['user_id', 'preset_key'])


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; dropping these fields would lose deleted-template recovery state.')
