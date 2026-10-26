"""Complete the governance operation permission menu registration."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_governance_permission_button'
down_revision = '20261002_governance_menu'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    exists = connection.execute(sa.text('SELECT menu_id FROM sys_menu WHERE menu_id = 1303')).scalar()
    if exists is None:
        connection.execute(
            sa.text(
                'INSERT INTO sys_menu '
                '(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, '
                'is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, '
                'update_by, update_time, remark) '
                "VALUES (1303, '处理质量问题', 1301, 2, '', NULL, '', '', 1, 0, 'F', '0', '0', "
                "'pipeline:governance:operate', '#', 'admin', CURRENT_TIMESTAMP, '', NULL, '')"
            )
        )


def downgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' in inspect(connection).get_table_names():
        connection.execute(sa.text('DELETE FROM sys_menu WHERE menu_id = 1303'))
