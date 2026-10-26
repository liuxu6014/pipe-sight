"""Register the governance menu and its explicit permissions."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_governance_menu'
down_revision = '20261002_governance_registry'
branch_labels = None
depends_on = None

MENU_ROWS = (
    (1300, '管网情报', 0, 20, 'pipeline', None, 'M', '0', '', 'data-analysis', '管网情报目录'),
    (
        1301,
        '数据治理',
        1300,
        1,
        'governance',
        'pipeline/governance/index',
        'C',
        '0',
        'pipeline:governance:list',
        'build',
        '管网情报数据治理菜单',
    ),
    (1302, '刷新质量扫描', 1301, 1, '', None, 'F', '0', 'pipeline:governance:sync', '#', ''),
    (1303, '处理质量问题', 1301, 2, '', None, 'F', '0', 'pipeline:governance:operate', '#', ''),
)


def _insert_menu(connection: sa.Connection, row: tuple[object, ...]) -> None:
    menu_id, menu_name, parent_id, order_num, path, component, menu_type, visible, perms, icon, remark = row
    exists = connection.execute(
        sa.text(
            'SELECT menu_id FROM sys_menu '
            'WHERE menu_id = :menu_id OR '
            '(menu_type <> \'F\' AND parent_id = :parent_id AND path = :path AND menu_type = :menu_type) '
            'LIMIT 1'
        ),
        {'menu_id': menu_id, 'parent_id': parent_id, 'path': path, 'menu_type': menu_type},
    ).scalar()
    if exists is not None:
        return
    connection.execute(
        sa.text(
            'INSERT INTO sys_menu '
            '(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, '
            'is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, '
            'update_by, update_time, remark) '
            'VALUES (:menu_id, :menu_name, :parent_id, :order_num, :path, :component, \'\', \'\', '
            '1, 0, :menu_type, :visible, \'0\', :perms, :icon, \'admin\', CURRENT_TIMESTAMP, \'\', NULL, :remark)'
        ),
        {
            'menu_id': menu_id,
            'menu_name': menu_name,
            'parent_id': parent_id,
            'order_num': order_num,
            'path': path,
            'component': component,
            'menu_type': menu_type,
            'visible': visible,
            'perms': perms,
            'icon': icon,
            'remark': remark,
        },
    )


def upgrade() -> None:
    if context.is_offline_mode():
        return
    inspector = inspect(op.get_bind())
    if 'sys_menu' not in inspector.get_table_names():
        return
    connection = op.get_bind()
    for row in MENU_ROWS:
        _insert_menu(connection, row)


def downgrade() -> None:
    if context.is_offline_mode():
        return
    inspector = inspect(op.get_bind())
    if 'sys_menu' not in inspector.get_table_names():
        return
    connection = op.get_bind()
    menu_ids = tuple(row[0] for row in MENU_ROWS)
    if 'sys_role_menu' in inspector.get_table_names():
        connection.execute(
            sa.text('DELETE FROM sys_role_menu WHERE menu_id IN :menu_ids').bindparams(
                sa.bindparam('menu_ids', expanding=True)
            ),
            {'menu_ids': menu_ids},
        )
    connection.execute(
        sa.text('DELETE FROM sys_menu WHERE menu_id IN :menu_ids').bindparams(
            sa.bindparam('menu_ids', expanding=True)
        ),
        {'menu_ids': menu_ids},
    )
