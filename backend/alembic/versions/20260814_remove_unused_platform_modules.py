"""Remove organization, post, notice, and code-generator persistence.

Revision ID: 20260814_remove_unused_platform
Revises: 20260814_full_system_redesign
"""

from alembic import context, op
from sqlalchemy import inspect

revision = '20260814_remove_unused_platform'
down_revision = '20260814_full_system_redesign'
branch_labels = None
depends_on = None

REMOVED_MENU_PREDICATE = """(
    path IN ('dept', 'post', 'notice', 'gen')
    OR perms LIKE 'system:dept:%'
    OR perms LIKE 'system:post:%'
    OR perms LIKE 'system:notice:%'
    OR perms LIKE 'tool:gen:%'
    OR component LIKE 'system/dept/%'
    OR component LIKE 'system/post/%'
    OR component LIKE 'system/notice/%'
    OR component LIKE 'tool/gen/%'
)"""
REMOVED_TABLES = (
    'sys_user_post',
    'sys_role_dept',
    'gen_table_column',
    'sys_post',
    'sys_notice',
    'gen_table',
    'sys_dept',
)
REMOVED_COLUMNS = (
    ('sys_user', 'dept_id'),
    ('sys_role', 'dept_check_strictly'),
    ('ai_models', 'dept_id'),
    ('knowledge_files', 'dept_id'),
)


def _drop_column_online(table_name: str, column_name: str) -> None:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return
    if column_name not in {item['name'] for item in inspector.get_columns(table_name)}:
        return

    for foreign_key in inspector.get_foreign_keys(table_name):
        if column_name in foreign_key.get('constrained_columns', []) and foreign_key.get('name'):
            op.drop_constraint(foreign_key['name'], table_name, type_='foreignkey')
    for index in inspector.get_indexes(table_name):
        if column_name in index.get('column_names', []) and index.get('name'):
            op.drop_index(index['name'], table_name=table_name)
    op.drop_column(table_name, column_name)


def _upgrade_offline() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == 'postgresql':
        for table_name in REMOVED_TABLES:
            op.execute(f'DROP TABLE IF EXISTS {table_name} CASCADE')
        for table_name, column_name in REMOVED_COLUMNS:
            op.execute(f'ALTER TABLE {table_name} DROP COLUMN IF EXISTS {column_name} CASCADE')
    else:
        op.execute('SET FOREIGN_KEY_CHECKS = 0')
        for table_name in REMOVED_TABLES:
            op.execute(f'DROP TABLE IF EXISTS {table_name}')
        for table_name, column_name in REMOVED_COLUMNS:
            op.execute(f'ALTER TABLE {table_name} DROP COLUMN IF EXISTS {column_name}')
        op.execute('SET FOREIGN_KEY_CHECKS = 1')
    op.execute(
        'DELETE FROM sys_role_menu WHERE menu_id IN '
        f'(SELECT menu_id FROM sys_menu WHERE {REMOVED_MENU_PREDICATE})'
    )
    op.execute(f'DELETE FROM sys_menu WHERE {REMOVED_MENU_PREDICATE}')


def upgrade() -> None:
    if context.is_offline_mode():
        _upgrade_offline()
        return

    inspector = inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    if 'sys_role_menu' in table_names and 'sys_menu' in table_names:
        op.execute(
            'DELETE FROM sys_role_menu WHERE menu_id IN '
            f'(SELECT menu_id FROM sys_menu WHERE {REMOVED_MENU_PREDICATE})'
        )
    if 'sys_menu' in table_names:
        op.execute(f'DELETE FROM sys_menu WHERE {REMOVED_MENU_PREDICATE}')

    for table_name in REMOVED_TABLES[:-1]:
        if table_name in set(inspect(op.get_bind()).get_table_names()):
            op.drop_table(table_name)
    for table_name, column_name in REMOVED_COLUMNS:
        _drop_column_online(table_name, column_name)
    if 'sys_dept' in set(inspect(op.get_bind()).get_table_names()):
        op.drop_table('sys_dept')


def downgrade() -> None:
    # The removed modules and their data are intentionally not recreated.
    return None
