"""Register the persistent PipeSight management menu tree without the removed QA menu."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_pipeline_menu_tree'
down_revision = '20261003_pipeline_source_task_review_permissions'
branch_labels = None
depends_on = None

MENU_ROWS = (
    (2000, '管网情报', 0, 5, 'pipeline', None, 'M', '0', '', 'chart', '管网科技情报目录'),
    (2001, '工作台', 2000, 1, 'dashboard', 'pipeline/dashboard/index', 'C', '0', 'pipeline:dashboard:view', 'dashboard', '管网情报工作台'),
    (2002, '情报检索', 2000, 2, 'intelligence', 'pipeline/intelligence/index', 'C', '0', 'pipeline:intel:list', 'search', '新闻、公众号和论文统一检索'),
    (2003, '情报详情', 2000, 3, 'intelligence/detail', 'pipeline/intelligence/detail', 'C', '1', 'pipeline:intel:detail', 'list', '情报详情隐藏路由'),
    (2004, '数据源管理', 2000, 4, 'source', 'pipeline/source/index', 'C', '0', 'pipeline:source:list', 'link', '采集数据源管理'),
    (2005, '采集任务', 2000, 5, 'task', 'pipeline/task/index', 'C', '0', 'pipeline:task:list', 'job', '采集任务监控'),
    (2006, '日报周报', 2000, 6, 'report', 'pipeline/report/index', 'C', '0', 'pipeline:report:list', 'documentation', '日报、周报与科研报告'),
    (2008, '模板管理', 2000, 8, 'template', 'pipeline/template/index', 'C', '0', 'pipeline:template:list', 'documentation', '科研报告和周期简报模板'),
    (2009, '模型与 Prompt', 2000, 9, 'model', 'pipeline/model/index', 'C', '0', 'ai:model:list', 'ai', '模型路由与 Prompt 版本管理'),
)


def upgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    for menu_id, menu_name, parent_id, order_num, path, component, menu_type, visible, perms, icon, remark in MENU_ROWS:
        exists = connection.execute(
            sa.text(
                'SELECT menu_id FROM sys_menu '
                'WHERE menu_id = :menu_id OR '
                '(menu_type = :menu_type AND parent_id = :parent_id AND path = :path) LIMIT 1'
            ),
            {'menu_id': menu_id, 'menu_type': menu_type, 'parent_id': parent_id, 'path': path},
        ).scalar()
        if exists is not None:
            continue
        connection.execute(
            sa.text(
                'INSERT INTO sys_menu '
                '(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, '
                'is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, '
                'update_by, update_time, remark) '
                "VALUES (:menu_id, :menu_name, :parent_id, :order_num, :path, :component, '', '', "
                "1, 0, :menu_type, :visible, '0', :perms, :icon, 'admin', CURRENT_TIMESTAMP, '', NULL, :remark)"
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


def downgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    menu_ids = tuple(row[0] for row in MENU_ROWS)
    if 'sys_role_menu' in inspect(connection).get_table_names():
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
