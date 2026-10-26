"""Use Beijing wall-clock seconds for business audit timestamps only."""

from pathlib import Path

from alembic import context, op

from app.beijing_time_migration import migrate_beijing_audit_time

revision = '20261025_beijing_audit_time'
down_revision = '20261025_business_consistency'
branch_labels = None
depends_on = None


def upgrade() -> None:
    args = context.get_x_argument(as_dictionary=True)
    if not args.get('beijing_backup'):
        raise RuntimeError('Pass -x beijing_backup=/private/verified/backup-directory')
    migrate_beijing_audit_time(
        op.get_bind(), backup_dir=Path(args['beijing_backup']), allow_live=args.get('beijing_allow_live') == 'true'
    )


def downgrade() -> None:
    raise RuntimeError(
        'Restore the verified code/database pair; discarded sub-second precision cannot be reconstructed'
    )
