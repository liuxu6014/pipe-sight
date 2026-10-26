"""Add database leases for scheduled collection and external handoff workers."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_collection_execution_leases'
down_revision = '20261002_material_parse_leases'
branch_labels = None
depends_on = None


def _add_columns() -> None:
    op.add_column(
        'data_sources',
        sa.Column('collection_lease_owner', sa.String(128), nullable=True, comment='采集执行器租约持有者'),
    )
    op.add_column(
        'data_sources',
        sa.Column('collection_lease_until', sa.DateTime(), nullable=True, comment='采集执行器租约到期时间'),
    )
    op.add_column(
        'collection_runs',
        sa.Column('handoff_lease_owner', sa.String(128), nullable=True, comment='交接执行器租约持有者'),
    )
    op.add_column(
        'collection_runs',
        sa.Column('handoff_lease_until', sa.DateTime(), nullable=True, comment='交接执行器租约到期时间'),
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _add_columns()
        op.create_index(
            'idx_data_sources_collection_lease',
            'data_sources',
            ['enabled', 'status', 'collection_lease_until', 'update_time'],
        )
        op.create_index(
            'idx_collection_runs_handoff_lease',
            'collection_runs',
            ['handoff_status', 'handoff_lease_until', 'update_time'],
        )
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if not {'data_sources', 'collection_runs'}.issubset(tables):
        return
    source_columns = {item['name'] for item in inspector.get_columns('data_sources')}
    run_columns = {item['name'] for item in inspector.get_columns('collection_runs')}
    if 'collection_lease_owner' not in source_columns:
        op.add_column(
            'data_sources',
            sa.Column('collection_lease_owner', sa.String(128), nullable=True, comment='采集执行器租约持有者'),
        )
    if 'collection_lease_until' not in source_columns:
        op.add_column(
            'data_sources',
            sa.Column('collection_lease_until', sa.DateTime(), nullable=True, comment='采集执行器租约到期时间'),
        )
    if 'handoff_lease_owner' not in run_columns:
        op.add_column(
            'collection_runs',
            sa.Column('handoff_lease_owner', sa.String(128), nullable=True, comment='交接执行器租约持有者'),
        )
    if 'handoff_lease_until' not in run_columns:
        op.add_column(
            'collection_runs',
            sa.Column('handoff_lease_until', sa.DateTime(), nullable=True, comment='交接执行器租约到期时间'),
        )

    source_indexes = {item['name'] for item in inspect(bind).get_indexes('data_sources')}
    if 'idx_data_sources_collection_lease' not in source_indexes:
        op.create_index(
            'idx_data_sources_collection_lease',
            'data_sources',
            ['enabled', 'status', 'collection_lease_until', 'update_time'],
        )
    run_indexes = {item['name'] for item in inspect(bind).get_indexes('collection_runs')}
    if 'idx_collection_runs_handoff_lease' not in run_indexes:
        op.create_index(
            'idx_collection_runs_handoff_lease',
            'collection_runs',
            ['handoff_status', 'handoff_lease_until', 'update_time'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        op.drop_index('idx_collection_runs_handoff_lease', table_name='collection_runs')
        op.drop_index('idx_data_sources_collection_lease', table_name='data_sources')
        for table, column in (
            ('collection_runs', 'handoff_lease_until'),
            ('collection_runs', 'handoff_lease_owner'),
            ('data_sources', 'collection_lease_until'),
            ('data_sources', 'collection_lease_owner'),
        ):
            op.drop_column(table, column)
        return

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if 'collection_runs' in tables and 'idx_collection_runs_handoff_lease' in {
        item['name'] for item in inspector.get_indexes('collection_runs')
    }:
        op.drop_index('idx_collection_runs_handoff_lease', table_name='collection_runs')
    if 'data_sources' in tables and 'idx_data_sources_collection_lease' in {
        item['name'] for item in inspector.get_indexes('data_sources')
    }:
        op.drop_index('idx_data_sources_collection_lease', table_name='data_sources')
    if 'collection_runs' in tables:
        columns = {item['name'] for item in inspect(bind).get_columns('collection_runs')}
        for column in ('handoff_lease_until', 'handoff_lease_owner'):
            if column in columns:
                op.drop_column('collection_runs', column)
    if 'data_sources' in tables:
        columns = {item['name'] for item in inspect(bind).get_columns('data_sources')}
        for column in ('collection_lease_until', 'collection_lease_owner'):
            if column in columns:
                op.drop_column('data_sources', column)
