"""Register the pipeline Prompt and template permissions used by the management UI."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_pipeline_prompt_template_permissions'
down_revision = '20261003_digest_schedule_idempotency'
branch_labels = None
depends_on = None

# These are button permissions rather than a second navigation tree.  The
# existing model menu (118) is reused for Prompt controls, while template
# permissions remain assignable even when deployments use static frontend
# routes instead of importing the optional pipeline menu seed.
MENU_ROWS = (
    (2015, 'Prompt 查询', 118, 5, 'pipeline:prompt:list', 'Prompt版本查询'),
    (2016, 'Prompt 保存', 118, 6, 'pipeline:prompt:save', 'Prompt草稿保存'),
    (2017, 'Prompt 测试', 118, 7, 'pipeline:prompt:test', 'Prompt离线结构测试'),
    (2018, 'Prompt 发布', 118, 8, 'pipeline:prompt:publish', 'Prompt版本发布'),
    (2019, '模板查询', 2000, 8, 'pipeline:template:list', '模板版本查询'),
    (2020, '模板保存', 2000, 9, 'pipeline:template:save', '模板草稿保存'),
    (2021, '模板发布', 2000, 10, 'pipeline:template:publish', '模板版本发布与停用'),
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
