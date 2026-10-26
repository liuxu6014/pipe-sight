"""Add explicit security scan state to knowledge files."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_material_scan_state'
down_revision = '20261002_search_utf8_trgm'
branch_labels = None
depends_on = None


def _columns(bind: sa.engine.Connection) -> set[str]:
    return {item['name'] for item in inspect(bind).get_columns('knowledge_files')}


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column(
            'knowledge_files',
            sa.Column('scan_status', sa.String(32), nullable=False, server_default='pending'),
        )
        op.add_column('knowledge_files', sa.Column('scan_message', sa.String(500), nullable=True))
        op.add_column('knowledge_files', sa.Column('scan_time', sa.DateTime(), nullable=True))
        op.add_column('knowledge_files', sa.Column('scanner_name', sa.String(128), nullable=True))
        op.create_check_constraint(
            'ck_knowledge_files_scan_status',
            'knowledge_files',
            "scan_status IN ('pending', 'clean', 'quarantined', 'failed')",
        )
        op.create_index('idx_knowledge_files_scan_status_time', 'knowledge_files', ['scan_status', 'update_time'])
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'knowledge_files' not in inspector.get_table_names():
        return
    columns = _columns(bind)
    if 'scan_status' not in columns:
        op.add_column(
            'knowledge_files',
            sa.Column('scan_status', sa.String(32), nullable=False, server_default='pending'),
        )
    if 'scan_message' not in columns:
        op.add_column('knowledge_files', sa.Column('scan_message', sa.String(500), nullable=True))
    if 'scan_time' not in columns:
        op.add_column('knowledge_files', sa.Column('scan_time', sa.DateTime(), nullable=True))
    if 'scanner_name' not in columns:
        op.add_column('knowledge_files', sa.Column('scanner_name', sa.String(128), nullable=True))

    constraints = {item['name'] for item in inspect(bind).get_check_constraints('knowledge_files')}
    if 'ck_knowledge_files_scan_status' not in constraints:
        op.create_check_constraint(
            'ck_knowledge_files_scan_status',
            'knowledge_files',
            "scan_status IN ('pending', 'clean', 'quarantined', 'failed')",
        )
    indexes = {item['name'] for item in inspect(bind).get_indexes('knowledge_files')}
    if 'idx_knowledge_files_scan_status_time' not in indexes:
        op.create_index('idx_knowledge_files_scan_status_time', 'knowledge_files', ['scan_status', 'update_time'])


def downgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        op.drop_index('idx_knowledge_files_scan_status_time', table_name='knowledge_files')
        op.drop_constraint('ck_knowledge_files_scan_status', 'knowledge_files', type_='check')
        for column_name in ('scanner_name', 'scan_time', 'scan_message', 'scan_status'):
            op.drop_column('knowledge_files', column_name)
        return
    inspector = inspect(bind)
    if 'knowledge_files' not in inspector.get_table_names():
        return
    indexes = {item['name'] for item in inspector.get_indexes('knowledge_files')}
    if 'idx_knowledge_files_scan_status_time' in indexes:
        op.drop_index('idx_knowledge_files_scan_status_time', table_name='knowledge_files')
    constraints = {item['name'] for item in inspector.get_check_constraints('knowledge_files')}
    if 'ck_knowledge_files_scan_status' in constraints:
        op.drop_constraint('ck_knowledge_files_scan_status', 'knowledge_files', type_='check')
    columns = _columns(bind)
    for column_name in ('scanner_name', 'scan_time', 'scan_message', 'scan_status'):
        if column_name in columns:
            op.drop_column('knowledge_files', column_name)
