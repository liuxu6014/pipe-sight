"""Restore RuoYi sys_* names without changing fields or business tables."""

import hashlib
import json
from pathlib import Path

from alembic import context, op

from app.ruoyi_table_names import restore_ruoyi_names

revision = '20261025_restore_ruoyi_names'
down_revision = '20261025_compact_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    args = context.get_x_argument(as_dictionary=True)
    if not args.get('ruoyi_backup'):
        raise RuntimeError('Pass -x ruoyi_backup=/private/backup-directory')
    root = Path(args['ruoyi_backup']).resolve()
    if not root.is_dir() or root.stat().st_mode & 0o077:
        raise RuntimeError('Backup directory must be private')
    manifest = json.loads((root / 'database-before.json').read_text())
    if hashlib.sha256((root / 'database-before.dump').read_bytes()).hexdigest() != manifest['sha256']:
        raise RuntimeError('Backup dump SHA-256 mismatch')
    restore_ruoyi_names(op.get_bind(), manifest=manifest, allow_live=args.get('ruoyi_allow_live') == 'true')


def downgrade() -> None:
    raise RuntimeError('RuoYi names are required; restore the verified backup for rollback')
