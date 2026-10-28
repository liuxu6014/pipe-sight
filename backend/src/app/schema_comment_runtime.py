"""Current compact-v5 comment SQL and catalog verification; no ORM imports."""


import sqlalchemy as sa

from app.schema_comments import (
    COLUMN_COMMENTS,
    FRAMEWORK_TABLE_NAMES,
    OPTIONAL_TABLE_NAMES,
    TABLE_COMMENTS,
    VIEW_COMMENTS,
)
from app.schema_contract import SchemaPrerequisiteError
from app.schema_migration import _inventory, _q, assert_rehearsal, normalise_optional_tables


def _comment_sql(kind: str, table: str, column: str | None, comment: str) -> str:
    identifier = 'public.' + _q(table) + ('.' + _q(column) if column is not None else '')
    literal = "'" + comment.replace("'", "''") + "'"
    return f'COMMENT ON {kind} {identifier} IS {literal};'


def render_comment_sql() -> str:
    """Deterministic canonical SQL; optional/framework/catalog objects guarded."""
    lines = [
        '-- compact-v6中文注释；12业务PK及引用FK为BIGINT，共享business_id_seq；若依表字段不变。',
        '-- 27个业务created_at/updated_at为北京时间timestamp(0)无时区；其他运行时间字段保持原类型。',
        '-- 普通不透明令牌保留；系统幂等键内嵌ID、显式JSON引用及语义指纹按实体映射核验。',
        '-- 27张基线表320字段，2张保留功能表23字段；共29张物理表343字段。',
        '-- 仅COMMENT及存在性保护块；调用方管理事务，不修改字段、约束或业务数据。',
        '',
    ]
    for name, comment in TABLE_COMMENTS.items():
        statements = [_comment_sql('TABLE', name, None, comment)]
        statements.extend(_comment_sql('COLUMN', name, col, text) for col, text in COLUMN_COMMENTS[name].items())
        if name in (*OPTIONAL_TABLE_NAMES, *FRAMEWORK_TABLE_NAMES):
            lines.extend(_guard_comments(name, statements))
        else:
            lines.extend(statements)
        lines.append('')
    for name, spec in VIEW_COMMENTS.items():
        statements = [_comment_sql('VIEW', name, None, spec['comment'])]
        statements.extend(_comment_sql('COLUMN', name, col, text) for col, text in spec['columns'].items())
        lines.extend(_guard_comments(name, statements))
        lines.append('')
    return '\n'.join(lines) + '\n'


def _guard_comments(name: str, statements: list[str]) -> list[str]:
    tag = f'$pipesight_{name}_comments$'
    return [f'DO {tag}', 'BEGIN', f"    IF to_regclass('public.{name}') IS NOT NULL THEN",
            *('        ' + statement for statement in statements), '    END IF;', 'END;', f'{tag};']


def verify_schema_comments(bind: sa.Connection, *, optional_tables: tuple[str, ...] = OPTIONAL_TABLE_NAMES) -> dict:
    """Verify PostgreSQL table and field comments against the same pure data."""
    names = set(TABLE_COMMENTS) - (set(OPTIONAL_TABLE_NAMES) - set(normalise_optional_tables(optional_tables)))
    inspector = sa.inspect(bind)
    columns = 0
    for name in sorted(names):
        if inspector.get_table_comment(name, schema='public')['text'] != TABLE_COMMENTS[name]:
            raise SchemaPrerequisiteError(f'Database table comment mismatch: {name}')
        actual = {c['name']: c.get('comment') for c in inspector.get_columns(name, schema='public')}
        if actual != COLUMN_COMMENTS[name]:
            raise SchemaPrerequisiteError(f'Database column comments mismatch: {name}')
        columns += len(actual)
    views = set(inspector.get_view_names(schema='public')) & set(VIEW_COMMENTS)
    for name in views:
        actual_table_comment = bind.execute(sa.text('SELECT obj_description(to_regclass(:name))'),
                                            {'name': 'public.' + name}).scalar_one()
        actual = {c['name']: c.get('comment') for c in inspector.get_columns(name, schema='public')}
        if actual_table_comment != VIEW_COMMENTS[name]['comment'] or actual != VIEW_COMMENTS[name]['columns']:
            raise SchemaPrerequisiteError(f'Database catalog view comments mismatch: {name}')
    return {'tables': len(names), 'columns': columns, 'views': len(views)}


def apply_schema_comments(bind: sa.Connection, *, optional_tables: tuple[str, ...] = OPTIONAL_TABLE_NAMES,
                          allow_live: bool = False) -> dict:
    """Comment-only, atomic application; no application imports or business DML."""
    if not bind.in_transaction():
        raise SchemaPrerequisiteError('A caller-owned transaction is required')
    assert_rehearsal(bind, allow_live=allow_live)
    expected = set(TABLE_COMMENTS) - (set(OPTIONAL_TABLE_NAMES) - set(normalise_optional_tables(optional_tables)))
    if _inventory(bind) != {'public.' + name for name in expected}:
        raise SchemaPrerequisiteError('Comment application requires canonical table inventory')
    inspector = sa.inspect(bind)
    for name in expected:
        if {c['name'] for c in inspector.get_columns(name, schema='public')} != set(COLUMN_COMMENTS[name]):
            raise SchemaPrerequisiteError(f'Comment application field mismatch: {name}')
    with bind.begin_nested():
        # asyncpg prepares one SQL command at a time. The generated psql script
        # remains useful offline, but must not be submitted as one prepared query.
        for name in TABLE_COMMENTS:
            if name not in expected:
                continue
            bind.exec_driver_sql(_comment_sql('TABLE', name, None, TABLE_COMMENTS[name]))
            for column, comment in COLUMN_COMMENTS[name].items():
                bind.exec_driver_sql(_comment_sql('COLUMN', name, column, comment))
        views = set(inspector.get_view_names(schema='public'))
        for name, spec in VIEW_COMMENTS.items():
            if name not in views:
                continue
            bind.exec_driver_sql(_comment_sql('VIEW', name, None, spec['comment']))
            for column, comment in spec['columns'].items():
                bind.exec_driver_sql(_comment_sql('COLUMN', name, column, comment))
        return verify_schema_comments(bind, optional_tables=optional_tables)
