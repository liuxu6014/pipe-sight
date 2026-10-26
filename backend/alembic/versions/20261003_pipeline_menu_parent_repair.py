"""Attach the PipeSight menu rows to the actual existing pipeline root."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_pipeline_menu_parent_repair'
down_revision = '20261003_pipeline_menu_tree'
branch_labels = None
depends_on = None

PAGE_IDS = (2001, 2002, 2003, 2004, 2005, 2006, 2008, 2009)


def _pipeline_root(connection: sa.Connection) -> int | None:
    return connection.execute(
        sa.text(
            "SELECT menu_id FROM sys_menu "
            "WHERE parent_id = 0 AND menu_type = 'M' AND path = 'pipeline' "
            'ORDER BY menu_id LIMIT 1'
        )
    ).scalar()


def upgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    root_id = _pipeline_root(connection)
    if root_id is None:
        return
    connection.execute(
        sa.text(
            'UPDATE sys_menu SET parent_id = :root_id '
            'WHERE menu_id IN :menu_ids AND parent_id IN (0, 2000)'
        ).bindparams(sa.bindparam('menu_ids', expanding=True)),
        {'root_id': root_id, 'menu_ids': PAGE_IDS},
    )
    connection.execute(
        sa.text(
            'UPDATE sys_menu SET parent_id = :parent_id '
            'WHERE menu_id IN (2015, 2016, 2017, 2018)'
        ),
        {'parent_id': 2009},
    )
    connection.execute(
        sa.text(
            'UPDATE sys_menu SET parent_id = :parent_id '
            'WHERE menu_id IN (2019, 2020, 2021)'
        ),
        {'parent_id': 2008},
    )


def downgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    if 'sys_menu' not in inspect(connection).get_table_names():
        return
    connection.execute(
        sa.text('UPDATE sys_menu SET parent_id = 2000 WHERE menu_id IN :menu_ids').bindparams(
            sa.bindparam('menu_ids', expanding=True)
        ),
        {'menu_ids': PAGE_IDS},
    )
    connection.execute(
        sa.text('UPDATE sys_menu SET parent_id = 118 WHERE menu_id IN (2015, 2016, 2017, 2018)')
    )
    connection.execute(
        sa.text('UPDATE sys_menu SET parent_id = 2000 WHERE menu_id IN (2019, 2020, 2021)')
    )
