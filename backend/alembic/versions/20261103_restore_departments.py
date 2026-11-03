"""Restore native RuoYi departments without rewriting existing accounts."""

import sqlalchemy as sa
from alembic import op

revision = '20261103_restore_departments'
down_revision = '20261102_core_content_entities'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sys_dept',
        sa.Column('dept_id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('parent_id', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('ancestors', sa.String(500), nullable=False, server_default='0'),
        sa.Column('dept_name', sa.String(30), nullable=False),
        sa.Column('order_num', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leader', sa.String(20), nullable=True),
        sa.Column('phone', sa.String(11), nullable=True),
        sa.Column('email', sa.String(50), nullable=True),
        sa.Column('status', sa.String(1), nullable=False, server_default='0'),
        sa.Column('del_flag', sa.String(1), nullable=False, server_default='0'),
        sa.Column('create_by', sa.String(64), nullable=True),
        sa.Column('create_time', sa.DateTime(), nullable=True),
        sa.Column('update_by', sa.String(64), nullable=True),
        sa.Column('update_time', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_sys_dept_parent_id', 'sys_dept', ['parent_id'])
    op.create_check_constraint('ck_sys_dept_status', 'sys_dept', "status IN ('0', '1')")
    op.create_check_constraint('ck_sys_dept_del_flag', 'sys_dept', "del_flag IN ('0', '2')")
    op.create_index(
        'uq_sys_dept_active_name',
        'sys_dept',
        ['parent_id', 'dept_name'],
        unique=True,
        postgresql_where=sa.text("del_flag = '0'"),
    )
    op.add_column('sys_user', sa.Column('dept_id', sa.BigInteger(), nullable=True))
    op.create_index('ix_sys_user_dept_id', 'sys_user', ['dept_id'])
    op.create_foreign_key('fk_sys_user_dept_id', 'sys_user', 'sys_dept', ['dept_id'], ['dept_id'], ondelete='RESTRICT')

    # Explicit menu permissions for administrators only. Existing role grants stay unchanged.
    bind = op.get_bind()
    bind.execute(sa.text('LOCK TABLE sys_menu IN SHARE ROW EXCLUSIVE MODE'))
    parent = bind.execute(
        sa.text("SELECT parent_id FROM sys_menu WHERE component='system/user/index' ORDER BY id LIMIT 1")
    ).scalar_one()
    menu_id = bind.execute(sa.text('SELECT COALESCE(MAX(id), 0) + 1 FROM sys_menu')).scalar_one()
    entries = [('部门管理', 'dept', 'system/dept/index', 'C', 'system:dept:list', parent, 'tree')]
    entries += [
        (title, '', None, 'F', f'system:dept:{permission}', menu_id, '#')
        for title, permission in (
            ('部门查询', 'query'),
            ('部门新增', 'add'),
            ('部门修改', 'edit'),
            ('部门删除', 'remove'),
        )
    ]
    for offset, (name, path, component, kind, permission, parent_id, icon) in enumerate(entries):
        ident = menu_id + offset
        bind.execute(
            sa.text("""INSERT INTO sys_menu
            (id,name,parent_id,sort_order,path,component,type,visible,status,permissions,icon,is_frame,is_cache,created_by,created_at)
            VALUES (:id,:name,:parent,4,:path,:component,:kind,'0','0',:permission,:icon,1,0,'admin',CURRENT_TIMESTAMP)"""),
            {
                'id': ident,
                'name': name,
                'parent': parent_id,
                'path': path,
                'component': component,
                'kind': kind,
                'permission': permission,
                'icon': icon,
            },
        )
        bind.execute(
            sa.text(
                'INSERT INTO sys_role_menu(role_id,menu_id) SELECT id,:menu FROM sys_role WHERE id=1 ON CONFLICT DO NOTHING'
            ),
            {'menu': ident},
        )
    bind.execute(sa.text("SELECT setval(pg_get_serial_sequence('sys_menu','id'), (SELECT MAX(id) FROM sys_menu))"))

    from app.schema_comments import COLUMN_COMMENTS, TABLE_COMMENTS  # noqa: PLC0415

    for table in ('sys_dept', 'sys_user'):
        if table == 'sys_dept':
            op.execute(sa.schema.SetTableComment(sa.Table(table, sa.MetaData(), comment=TABLE_COMMENTS[table])))
        columns = COLUMN_COMMENTS[table] if table == 'sys_dept' else {'dept_id': COLUMN_COMMENTS[table]['dept_id']}
        for name, comment in columns.items():
            column = sa.Column(name, sa.String, comment=comment)
            sa.Table(table, sa.MetaData(), column)
            op.execute(sa.schema.SetColumnComment(column))


def downgrade() -> None:
    raise RuntimeError('Restore the verified backup; department assignments must not be discarded automatically.')
