"""Clear stale processing lease timestamps from terminal inbox rows."""

import sqlalchemy as sa
from alembic import op

revision = '20261003_clear_terminal_processing_leases'
down_revision = '20261003_normalize_filter_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """A terminal row must not look like it still owns a Worker lease."""
    op.execute(
        sa.text(
            """
            UPDATE news.hp_news
            SET processing_started_at = NULL
            WHERE processing_started_at IS NOT NULL
              AND processing_status IN ('pending', 'failed', 'completed', 'rejected')
            """
        )
    )


def downgrade() -> None:
    """Lease timestamps cannot be reconstructed after terminalization."""
