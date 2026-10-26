"""Register source, collection-task, and review permissions for role assignment."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_pipeline_source_task_review_permissions'
down_revision = '20261003_pipeline_prompt_template_permissions'
branch_labels = None
depends_on = None

MENU_ROWS = (
    (2022, '数据源查询', 2004, 1, 'pipeline:source:list', '数据源列表查询'),
    (2023, '数据源配置', 2004, 2, 'pipeline:source:save', '数据源创建、修改与启停'),
    (2024, '采集任务查询', 2005, 1, 'pipeline:task:list', '采集任务列表查询'),
    (2025, '采集任务运行', 2005, 2, 'pipeline:task:run', '采集任务运行与外部处理同步'),
    (2026, '审核队列查询', 2002, 3, 'pipeline:review:list', '内容审核队列查询'),
    (2027, '审核队列处理', 2002, 4, 'pipeline:review:operate', '内容审核动作'),
    (2028, '审核内容重处理', 2002, 5, 'pipeline:review:reprocess', '审核内容重新处理'),
)


def upgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    for menu_id, menu_name, parent_id, order_num, perms, remark in MENU_ROWS:
        exists = connection.execute(
            sa.text(
                'SELECT menu_id FROM sys_menu '
                'WHERE menu_id = :menu_id OR perms = :perms LIMIT 1'
            ),
            {'menu_id': menu_id, 'perms': perms},
        ).scalar()
        if exists is not None:
            continue
        connection.execute(
            sa.text(
                'INSERT INTO sys_menu '
                '(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, '
                'is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, '
                'update_by, update_time, remark) '
                "VALUES (:menu_id, :menu_name, :parent_id, :order_num, '', NULL, '', '', "
                "1, 0, 'F', '0', '0', :perms, '#', 'admin', CURRENT_TIMESTAMP, '', NULL, :remark)"
            ),
            {
                'menu_id': menu_id,
                'menu_name': menu_name,
                'parent_id': parent_id,
                'order_num': order_num,
                'perms': perms,
                'remark': remark,
            },
        )


def downgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    for menu_id, _, _, _, perms, _ in MENU_ROWS:
        connection.execute(
            sa.text('DELETE FROM sys_menu WHERE menu_id = :menu_id AND perms = :perms'),
            {'menu_id': menu_id, 'perms': perms},
        )
