"""Add report_assets.caption for AI-generated figure captions."""

from alembic import op
import sqlalchemy as sa

revision = '20261122_report_assets_caption'
down_revision = '20261122_papers_source_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    comments = COLUMN_COMMENTS['report_assets']
    op.add_column(
        'report_assets',
        sa.Column('caption', sa.Text(), nullable=True, comment=comments['caption']),
    )


def downgrade() -> None:
    op.drop_column('report_assets', 'caption')
