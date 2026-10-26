"""Add UTF-8 trigram search support for Chinese substring queries."""

from alembic import op
from sqlalchemy import text

revision = '20261002_search_utf8_trgm'
down_revision = '20261002_handoff_status_repair'
branch_labels = None
depends_on = None


_SEARCH_INDEXES = (
    (
        'idx_news_articles_search_utf8_trgm',
        'news_articles',
        "coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(body, '')",
    ),
    (
        'idx_papers_search_utf8_trgm',
        'papers',
        "coalesce(title, '') || ' ' || coalesce(abstract_text, '') || ' ' || coalesce(authors, '')",
    ),
    (
        'idx_knowledge_files_search_utf8_trgm',
        'knowledge_files',
        "coalesce(name, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(extracted_text, '')",
    ),
    (
        'idx_reports_search_utf8_trgm',
        'reports',
        "coalesce(title, '') || ' ' || coalesce(content, '') || ' ' || coalesce(report_type, '')",
    ),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    op.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION pipeline_utf8_hex(value TEXT)
            RETURNS TEXT
            LANGUAGE SQL
            IMMUTABLE
            PARALLEL SAFE
            AS $$
              SELECT encode(convert_to(coalesce(value, ''), 'UTF8'), 'hex')
            $$
            """
        )
    )
    for index_name, table_name, expression in _SEARCH_INDEXES:
        op.execute(
            text(
                f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                  ON {table_name} USING gin
                  ((pipeline_utf8_hex(lower({expression}))) gin_trgm_ops)
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    for index_name, _, _ in _SEARCH_INDEXES:
        op.execute(text(f'DROP INDEX IF EXISTS {index_name}'))
    op.execute(text('DROP FUNCTION IF EXISTS pipeline_utf8_hex(TEXT)'))
