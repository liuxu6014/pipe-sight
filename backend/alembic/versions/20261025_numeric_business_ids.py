"""Numeric business primary keys and all stored references, not framework IDs."""

import json
from pathlib import Path

from alembic import context, op

from app.numeric_id_migration import migrate_numeric_ids

revision = '20261025_numeric_business_ids'
down_revision = '20261025_restore_ruoyi_names'
branch_labels = None
depends_on = None


def upgrade():
    args = context.get_x_argument(as_dictionary=True)
    if not args.get('numeric_backup'):
        raise RuntimeError('Pass -x numeric_backup=/private/verified/backup-directory')
    root = Path(args['numeric_backup']).resolve()
    manifest = json.loads((root / 'database-before.json').read_text())
    migrate_numeric_ids(
        op.get_bind(), manifest=manifest, backup_dir=root, allow_live=args.get('numeric_allow_live') == 'true'
    )


def downgrade():
    raise RuntimeError('Restore the verified backup and code snapshot; no lossy reverse-ID inference')
