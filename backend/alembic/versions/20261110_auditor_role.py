"""Seed a read-only operations auditor role without assigning it to any account."""

import sqlalchemy as sa
from alembic import op

revision = '20261110_auditor_role'
down_revision = '20261107_template_report_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("""
        INSERT INTO sys_role (name, code, sort_order, data_scope, status, del_flag, created_by, created_at, remark)
        VALUES ('审计员', 'auditor', 3, '5', '0', '0', 'admin', CURRENT_TIMESTAMP, '只读查看操作日志和登录日志')
        ON CONFLICT (code) DO NOTHING
    """)
    )
    bind.execute(
        sa.text("""
        WITH RECURSIVE log_menus AS (
            SELECT id, parent_id FROM sys_menu
            WHERE permissions IN ('monitor:operlog:list', 'monitor:operlog:query', 'monitor:logininfor:list')
            UNION
            SELECT menu.id, menu.parent_id FROM sys_menu AS menu
            JOIN log_menus ON log_menus.parent_id = menu.id
        )
        INSERT INTO sys_role_menu (role_id, menu_id)
        SELECT role.id, log_menus.id FROM sys_role AS role CROSS JOIN log_menus
        WHERE role.code = 'auditor'
        ON CONFLICT DO NOTHING
    """)
    )


def downgrade() -> None:
    raise RuntimeError('回退审计员角色需先核对账号分配，避免自动移除既有授权。')
