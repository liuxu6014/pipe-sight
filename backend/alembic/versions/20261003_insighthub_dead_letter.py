"""Add an explicit dead-letter state for exhausted InsightHub processing jobs."""

from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_insighthub_dead_letter'
down_revision = '20261003_clear_terminal_processing_leases'
branch_labels = None
depends_on = None

_STATUS_CONSTRAINT = 'ck_hp_news_processing_status'
_STATUS_SQL = "processing_status IN ('pending', 'processing', 'completed', 'rejected', 'failed', 'dead_letter')"


def _replace_constraint(status_sql: str) -> None:
    if context.is_offline_mode():
        op.execute(f'ALTER TABLE news.hp_news DROP CONSTRAINT IF EXISTS {_STATUS_CONSTRAINT}')
        op.execute(
            f'ALTER TABLE news.hp_news ADD CONSTRAINT {_STATUS_CONSTRAINT} CHECK ({status_sql})'
        )
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'hp_news' not in inspector.get_table_names(schema='news'):
        return
    constraints = {
        item['name'] for item in inspector.get_check_constraints('hp_news', schema='news')
    }
    if _STATUS_CONSTRAINT in constraints:
        op.drop_constraint(
            _STATUS_CONSTRAINT,
            'hp_news',
            schema='news',
            type_='check',
        )
    op.create_check_constraint(
        _STATUS_CONSTRAINT,
        'hp_news',
        status_sql,
        schema='news',
    )


def upgrade() -> None:
    """Allow exhausted processing attempts to remain explicitly recoverable."""
    _replace_constraint(_STATUS_SQL)


def downgrade() -> None:
    """Fold dead-letter rows back to failed before restoring the old constraint."""
    if context.is_offline_mode():
        op.execute("UPDATE news.hp_news SET processing_status='failed' WHERE processing_status='dead_letter'")
    else:
        bind = op.get_bind()
        inspector = inspect(bind)
        if 'hp_news' in inspector.get_table_names(schema='news'):
            op.execute("UPDATE news.hp_news SET processing_status='failed' WHERE processing_status='dead_letter'")
    _replace_constraint("processing_status IN ('pending', 'processing', 'completed', 'rejected', 'failed')")
