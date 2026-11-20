"""Add private document classification without reprocessing existing files."""

import sqlalchemy as sa
from alembic import op

revision = '20261120_material_classification'
down_revision = '20261118_digest_categories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing files are deliberately not queued for paid model calls.
    op.add_column('knowledge_files', sa.Column('category_id', sa.BigInteger(), nullable=True))
    op.add_column(
        'knowledge_files',
        sa.Column('classification_status', sa.String(16), nullable=False, server_default='not_configured'),
    )
    op.add_column('knowledge_files', sa.Column('classification_error', sa.Text(), nullable=True))
    op.add_column('knowledge_files', sa.Column('classification_token', sa.String(32), nullable=True))
    op.add_column('knowledge_files', sa.Column('classification_updated_at', sa.DateTime(), nullable=True))
    op.create_foreign_key(
        'fk_knowledge_files_category_id', 'knowledge_files', 'categories', ['category_id'], ['id'], ondelete='RESTRICT'
    )
    op.create_check_constraint(
        'ck_knowledge_files_classification_status',
        'knowledge_files',
        "classification_status IN ('queued','running','completed','failed','not_configured')",
    )
    op.drop_constraint('ck_categories_applies_to', 'categories', type_='check')
    op.create_check_constraint(
        'ck_categories_applies_to', 'categories', "applies_to IN ('news','paper','document','all')"
    )
    op.create_index('idx_knowledge_files_classification_queue', 'knowledge_files', ['classification_status', 'id'])


def downgrade() -> None:
    raise RuntimeError('Restore the verified backup; downgrade would discard saved document classifications.')
