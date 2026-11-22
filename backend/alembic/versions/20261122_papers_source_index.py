"""Index papers by source for provenance lookups and parity with news_articles."""

from alembic import op

revision = '20261122_papers_source_index'
down_revision = '20261122_source_deleted_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('idx_papers_source_id', 'papers', ['source_id'])


def downgrade() -> None:
    op.drop_index('idx_papers_source_id', table_name='papers')
