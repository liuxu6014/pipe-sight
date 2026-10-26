"""Normalize legacy PipeSight filter audit snapshots."""

import sqlalchemy as sa
from alembic import op

revision = '20261003_normalize_filter_audit'
down_revision = '20261003_report_export_permission'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make existing Worker-completed snapshots follow the current contract."""
    op.execute(
        sa.text(
            """
            WITH source AS (
                SELECT news_id, create_time, filter_result::jsonb AS payload
                FROM news.hp_news
                WHERE filter_result IS JSON
                  AND filter_result::jsonb #>> '{workerExecution,mode}' = 'llm'
            ), normalized AS (
                SELECT
                    news_id, create_time,
                    payload || jsonb_build_object(
                        'preFilter', COALESCE(
                            payload->'preFilter',
                            jsonb_strip_nulls(jsonb_build_object(
                                'mode', payload->'mode',
                                'executionMode', payload->'executionMode',
                                'promptApplied', payload->'promptApplied',
                                'decision', payload->'decision',
                                'fallback', payload->'fallback'
                            ))
                        ),
                        'mode', 'llm',
                        'executionMode', CASE
                            WHEN payload #>> '{workerExecution,fallbackUsed}' = 'true'
                            THEN 'llm-fallback'
                            ELSE 'llm'
                        END,
                        'promptApplied', true,
                        'decision', COALESCE(
                            payload #> '{workerExecution,decision}',
                            payload->'decision'
                        )
                    ) AS payload
                FROM source
            )
            UPDATE news.hp_news AS target
            SET filter_result = normalized.payload::text
            FROM normalized
            WHERE target.news_id = normalized.news_id
              AND target.create_time = normalized.create_time
            """
        )
    )


def downgrade() -> None:
    """Audit normalization is intentionally not reversed; source data is retained in preFilter."""
