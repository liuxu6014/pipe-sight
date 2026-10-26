"""Register the explicit report publication button permission."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_report_publication_permission'
down_revision = '20261003_digest_holiday_policy'
branch_labels = None
depends_on = None

MENU_ID = 2014
PERMISSION = 'pipeline:report:publish'


def upgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    exists = connection.execute(
        sa.text(
            'SELECT menu_id FROM sys_menu '
            'WHERE menu_id = :menu_id OR (parent_id = 2006 AND menu_type = \'F\' AND perms = :perms) '
            'LIMIT 1'
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
            "VALUES (:menu_id, '报告发布', 2006, 2, '', NULL, '', '', 1, 0, 'F', '0', '0', "
            ":perms, '#', 'admin', CURRENT_TIMESTAMP, '', NULL, '报告正式发布与撤销发布')"
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
