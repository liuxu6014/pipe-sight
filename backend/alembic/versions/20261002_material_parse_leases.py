"""Add durable parse queue lease state to knowledge files."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_material_parse_leases'
down_revision = '20261002_research_dead_letter'
branch_labels = None
depends_on = None


def _columns(bind: sa.engine.Connection) -> set[str]:
    return {item['name'] for item in inspect(bind).get_columns('knowledge_files')}


def _add_columns() -> None:
    op.add_column(
        'knowledge_files',
        sa.Column('parse_attempt_count', sa.Integer(), nullable=False, server_default='0', comment='解析尝试次数'),
    )
    op.add_column(
        'knowledge_files',
        sa.Column('parse_lease_owner', sa.String(128), nullable=True, comment='解析执行器租约持有者'),
    )
    op.add_column(
        'knowledge_files',
        sa.Column('parse_lease_until', sa.DateTime(), nullable=True, comment='解析执行器租约到期时间'),
    )
    op.add_column(
        'knowledge_files',
        sa.Column('parse_next_retry_at', sa.DateTime(), nullable=True, comment='下次解析重试时间'),
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _add_columns()
        op.create_check_constraint(
            'ck_knowledge_files_parse_attempt_count',
            'knowledge_files',
            'parse_attempt_count >= 0',
        )
        op.create_index(
            'idx_knowledge_files_parse_dispatch',
            'knowledge_files',
            ['parse_status', 'scan_status', 'parse_next_retry_at', 'parse_lease_until', 'update_time'],
        )
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'knowledge_files' not in inspector.get_table_names():
        return
    columns = _columns(bind)
    if 'parse_attempt_count' not in columns:
        _add_columns()
    constraints = {item['name'] for item in inspect(bind).get_check_constraints('knowledge_files')}
    if 'ck_knowledge_files_parse_attempt_count' not in constraints:
        op.create_check_constraint(
            'ck_knowledge_files_parse_attempt_count',
            'knowledge_files',
            'parse_attempt_count >= 0',
        )
    indexes = {item['name'] for item in inspect(bind).get_indexes('knowledge_files')}
    if 'idx_knowledge_files_parse_dispatch' not in indexes:
        op.create_index(
            'idx_knowledge_files_parse_dispatch',
            'knowledge_files',
            ['parse_status', 'scan_status', 'parse_next_retry_at', 'parse_lease_until', 'update_time'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        op.drop_index('idx_knowledge_files_parse_dispatch', table_name='knowledge_files')
        op.drop_constraint('ck_knowledge_files_parse_attempt_count', 'knowledge_files', type_='check')
        for column_name in ('parse_next_retry_at', 'parse_lease_until', 'parse_lease_owner', 'parse_attempt_count'):
            op.drop_column('knowledge_files', column_name)
        return

    inspector = inspect(bind)
    if 'knowledge_files' not in inspector.get_table_names():
        return
    indexes = {item['name'] for item in inspector.get_indexes('knowledge_files')}
    if 'idx_knowledge_files_parse_dispatch' in indexes:
        op.drop_index('idx_knowledge_files_parse_dispatch', table_name='knowledge_files')
    constraints = {item['name'] for item in inspector.get_check_constraints('knowledge_files')}
    if 'ck_knowledge_files_parse_attempt_count' in constraints:
        op.drop_constraint('ck_knowledge_files_parse_attempt_count', 'knowledge_files', type_='check')
    columns = _columns(bind)
    for column_name in ('parse_next_retry_at', 'parse_lease_until', 'parse_lease_owner', 'parse_attempt_count'):
        if column_name in columns:
            op.drop_column('knowledge_files', column_name)
