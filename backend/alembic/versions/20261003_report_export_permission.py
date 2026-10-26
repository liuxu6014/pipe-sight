"""Register the explicit backend-report export permission."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_report_export_permission'
down_revision = '20261003_pipeline_menu_parent_repair'
branch_labels = None
depends_on = None

MENU_ID = 2013
PERMISSION = 'pipeline:report:export'


def upgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    exists = connection.execute(
        sa.text(
            'SELECT menu_id FROM sys_menu '
            'WHERE menu_id = :menu_id OR perms = :perms LIMIT 1'
        ),
        {'menu_id': MENU_ID, 'perms': PERMISSION},
    ).scalar()
    if exists is not None:
        return
    connection.execute(
        sa.text(
            'INSERT INTO sys_menu '
            '(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, '
            'is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, '
            'update_by, update_time, remark) '
            "VALUES (:menu_id, '报告导出', 2006, 1, '', NULL, '', '', 1, 0, 'F', '0', '0', "
            ":perms, '#', 'admin', CURRENT_TIMESTAMP, '', NULL, '后台报告文件导出')"
        ),
        {'menu_id': MENU_ID, 'perms': PERMISSION},
    )


def downgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' in inspect(connection).get_table_names():
        connection.execute(
            sa.text('DELETE FROM sys_menu WHERE menu_id = :menu_id AND perms = :perms'),
            {'menu_id': MENU_ID, 'perms': PERMISSION},
        )
