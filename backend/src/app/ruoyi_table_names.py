"""Restore only RuoYi's physical table names, without rewriting any row/column."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from app.schema_comments_v2 import COLUMN_COMMENTS, TABLE_COMMENTS

RUOYI_TABLE_NAMES = {
    'users': 'sys_user',
    'roles': 'sys_role',
    'menus': 'sys_menu',
    'user_roles': 'sys_user_role',
    'role_menus': 'sys_role_menu',
    'settings': 'sys_config',
    'dict_types': 'sys_dict_type',
    'dict_items': 'sys_dict_data',
    'login_logs': 'sys_logininfor',
    'operation_logs': 'sys_oper_log',
    'scheduled_jobs': 'sys_job',
    'job_logs': 'sys_job_log',
}


def inventory(bind: sa.Connection) -> set[str]:
    return set(bind.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())


def row_fingerprints(bind: sa.Connection, names: set[str]) -> dict[str, list[Any]]:
    result = {}
    for name in sorted(names):
        if not name.replace('_', '').isalnum():
            raise ValueError('Unexpected identifier')
        result[name] = list(bind.execute(sa.text(
            "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
            f'(SELECT md5(row_to_json(t)::text) h FROM public."{name}" t)s'
        )).one())
    return result


def _physical_snapshot(bind: sa.Connection) -> dict[str, list[tuple]]:
    queries = {
        'tables': """SELECT c.oid,c.relowner,c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                     WHERE n.nspname='public' AND c.relkind IN ('r','p','S') ORDER BY c.oid""",
        'columns': """SELECT a.attrelid,a.attnum,a.attname,a.atttypid,a.atttypmod,a.attnotnull,a.attidentity,
                              a.attgenerated,a.attacl::text,pg_get_expr(d.adbin,d.adrelid)
                       FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
                       JOIN pg_namespace n ON n.oid=c.relnamespace
                       LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                       WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped
                       ORDER BY a.attrelid,a.attnum""",
        'constraints': """SELECT c.oid,c.conrelid,c.confrelid,c.contype,c.conkey,c.confkey,c.confdeltype,c.confupdtype,c.convalidated
                           FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
                           WHERE n.nspname='public' ORDER BY c.oid""",
        'indexes': """SELECT i.indexrelid,i.indrelid,i.indkey::text,i.indisunique,i.indisvalid
                       FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid
                       JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY i.indexrelid""",
    }
    return {key: [tuple(row) for row in bind.execute(sa.text(query))] for key, query in queries.items()}


def restore_ruoyi_names(bind: sa.Connection, *, manifest: dict, allow_live: bool = False) -> dict:
    """Caller owns the outer transaction; refuse drift or a partial rename."""
    if not bind.in_transaction():
        raise RuntimeError('A caller-owned transaction is required')
    url = bind.engine.url
    if not allow_live and not (url.host in {'localhost', '127.0.0.1'} and url.port == 19432):
        raise RuntimeError('Live destination requires explicit ruoyi_allow_live=true')
    target = set(TABLE_COMMENTS)
    source = (target - set(RUOYI_TABLE_NAMES.values())) | set(RUOYI_TABLE_NAMES)
    if len(target) != 29 or not set(RUOYI_TABLE_NAMES.values()) <= target:
        raise RuntimeError('Runtime comment contract must describe the 29-table RuoYi target')
    if manifest['revision'] != '20261025_compact_schema' or set(manifest['tables']) != source:
        raise RuntimeError('Backup must describe the pre-correction 29-table schema')
    with bind.begin_nested():
        bind.exec_driver_sql("SET LOCAL lock_timeout='5s'")
        bind.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
        bind.exec_driver_sql('SELECT pg_advisory_xact_lock(20261025, 29)')
        if inventory(bind) != source:
            raise RuntimeError('Unexpected source tables; refusing partial or repeated rename')
        bind.exec_driver_sql('LOCK TABLE ' + ','.join('public."' + name + '"' for name in sorted(source)) + ' IN ACCESS EXCLUSIVE MODE')
        before_rows = row_fingerprints(bind, source)
        if before_rows != manifest['fingerprints']:
            raise RuntimeError('Database changed since backup; take a fresh stopped-write snapshot')
        before = _physical_snapshot(bind)
        for old, new in RUOYI_TABLE_NAMES.items():
            bind.exec_driver_sql(f'ALTER TABLE public."{old}" RENAME TO "{new}"')
        if inventory(bind) != target or _physical_snapshot(bind) != before:
            raise RuntimeError('Rename changed columns, ownership, grants, constraints or indexes')
        expected_rows = {RUOYI_TABLE_NAMES.get(name, name): value for name, value in before_rows.items()}
        if row_fingerprints(bind, target) != expected_rows:
            raise RuntimeError('Rows changed during table-name correction')
        inspector = sa.inspect(bind)
        for name in sorted(target):
            if {column['name'] for column in inspector.get_columns(name, schema='public')} != set(COLUMN_COMMENTS[name]):
                raise RuntimeError('Unexpected target columns: ' + name)
            comment = TABLE_COMMENTS[name].replace("'", "''")
            bind.exec_driver_sql(f'COMMENT ON TABLE public."{name}" IS \'{comment}\'')
            for column, value in COLUMN_COMMENTS[name].items():
                value = value.replace("'", "''")
                bind.exec_driver_sql(f'COMMENT ON COLUMN public."{name}"."{column}" IS \'{value}\'')
        if _physical_snapshot(bind) != before or row_fingerprints(bind, target) != expected_rows:
            raise RuntimeError('Comment synchronization changed protected data or structure')
        return {'tables': len(target), 'renamed_tables': len(RUOYI_TABLE_NAMES),
                'columns_unchanged': True, 'all_rows_unchanged': True,
                'object_ids_constraints_indexes_ownership_acl_unchanged': True}
