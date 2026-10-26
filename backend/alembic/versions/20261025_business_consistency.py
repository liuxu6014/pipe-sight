"""Align business defaults, indexes and integrity checks without changing RuoYi."""

from pathlib import Path

from alembic import context, op

from app.business_schema_migration import migrate_business_consistency

revision = '20261025_business_consistency'
down_revision = '20261025_numeric_business_ids'
branch_labels = None
depends_on = None


def upgrade() -> None:
    args = context.get_x_argument(as_dictionary=True)
    if not args.get('business_backup'):
        raise RuntimeError('Pass -x business_backup=/private/verified/backup-directory')
    migrate_business_consistency(
        op.get_bind(), backup_dir=Path(args['business_backup']), allow_live=args.get('business_allow_live') == 'true'
    )


def downgrade() -> None:
    raise RuntimeError('Restore the verified code/database pair; do not weaken business integrity silently')
