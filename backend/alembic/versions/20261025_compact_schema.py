"""Apply approved compact-v1 after explicit source/archive gates.

Prepare the retirement archive with app.schema_migration.preflight/archive_plan.
Pass -x compact_archive=/private/path -x compact_archive_sha256=...,
-x compact_source_snapshot=/private/database-before.json and
-x historical_timezone=Asia/Shanghai. By default only the isolated rehearsal
endpoint is accepted. A live run additionally requires -x compact_allow_live=true
and an explicit invocation by the rollout owner; this revision never reads .env.
"""

import json
from pathlib import Path

from alembic import context, op

from app.schema_migration import migrate

revision = '20261025_compact_schema'
down_revision = '20261025_retire_processing_views'
branch_labels = None
depends_on = None


def upgrade() -> None:
    args = context.get_x_argument(as_dictionary=True)
    required = ('compact_archive', 'compact_archive_sha256', 'compact_source_snapshot', 'historical_timezone')
    if not all(args.get(key) for key in required):
        raise RuntimeError('compact_archive, compact_archive_sha256, compact_source_snapshot and historical_timezone are required')
    archive = json.loads(Path(args['compact_archive']).read_bytes())
    summary = archive['summary']
    migrate(
        op.get_bind(), archive_path=args['compact_archive'],
        archive_sha256=args['compact_archive_sha256'],
        historical_timezone=args['historical_timezone'],
        expected_source_fingerprints=summary['source_fingerprints'],
        source_snapshot=json.loads(Path(args['compact_source_snapshot']).read_bytes()),
        optional_tables=tuple(summary['optional_tables']),
        allow_live=args.get('compact_allow_live') == 'true',
    )


def downgrade() -> None:
    raise RuntimeError('Restore the verified pre-migration backup; compact migration has no lossy downgrade')
