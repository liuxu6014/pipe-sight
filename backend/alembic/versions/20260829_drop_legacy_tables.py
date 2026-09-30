"""Remove empty legacy PipeSight table names after the domain rename."""

from alembic import context, op
from sqlalchemy import inspect, text


revision = '20260829_drop_legacy_tables'
down_revision = '20260829_simplify_user_role_seed'
branch_labels = None
depends_on = None

LEGACY_TABLES = (
    'pipeline_material',
    'pipeline_report',
    'pipeline_report_version',
    'pipeline_research_job',
    'pipeline_workspace_item',
)


def upgrade() -> None:
    # Offline SQL cannot inspect row counts safely; the current SQL bootstrap
    # does not create these tables, so cleanup is only needed online.
    if context.is_offline_mode():
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    for table_name in LEGACY_TABLES:
        if table_name not in inspector.get_table_names():
            continue
        row_count = bind.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar_one()
        if row_count:
            print(f'[WARN] 保留非空遗留表 {table_name}（{row_count} 行），请完成数据迁移后再删除')
            continue
        op.drop_table(table_name)
        inspector = inspect(bind)


def downgrade() -> None:
    # Legacy tables were superseded by the explicit domain tables and are not recreated.
    return None
