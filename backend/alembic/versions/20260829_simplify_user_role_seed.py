"""Keep the built-in ordinary-user role out of the admin menu tree."""

from alembic import context, op
from sqlalchemy import inspect, text

revision = '20260829_simplify_user_role_seed'
down_revision = '20260824_external_processing_handoff'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        dialect = op.get_bind().dialect.name
        if dialect == 'postgresql':
            op.execute('ALTER TABLE sys_oper_log DROP COLUMN IF EXISTS dept_name')
        else:
            op.execute('ALTER TABLE sys_oper_log DROP COLUMN IF EXISTS dept_name')
        op.execute(
            "DELETE FROM sys_role_menu WHERE role_id IN "
            "(SELECT role_id FROM sys_role WHERE role_key IN ('common', 'user'))"
        )
        op.execute(
            "UPDATE sys_role SET role_name = '普通用户', remark = '普通用户' "
            "WHERE role_key = 'common' AND role_name = '普通角色'"
        )
        return

    tables = set(inspect(op.get_bind()).get_table_names())
    if 'sys_oper_log' in tables:
        columns = {column['name'] for column in inspect(op.get_bind()).get_columns('sys_oper_log')}
        if 'dept_name' in columns:
            op.drop_column('sys_oper_log', 'dept_name')
    if {'sys_role', 'sys_role_menu'}.issubset(tables):
        op.execute(
            text(
                "DELETE FROM sys_role_menu WHERE role_id IN "
                "(SELECT role_id FROM sys_role WHERE role_key IN ('common', 'user'))"
            )
        )
    if 'sys_role' in tables:
        op.execute(
            text(
                "UPDATE sys_role SET role_name = '普通用户', remark = '普通用户' "
                "WHERE role_key = 'common' AND role_name = '普通角色'"
            )
        )


def downgrade() -> None:
    # The old broad admin-menu grant is intentionally not restored.
    return None
