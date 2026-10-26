"""Backup-gated, metadata-only business consistency migration.

No foundation DDL, ID reassignment, data rewriting or compatibility objects.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import TYPE_CHECKING

import sqlalchemy as sa

from app.business_schema import (
    BUSINESS_TABLES,
    canonical_catalog,
    catalog,
    load_frozen,
    quote_identifier,
    schema_differences,
)

if TYPE_CHECKING:
    from pathlib import Path

REVISION = '20261025_business_consistency'
PREVIOUS_REVISION = '20261025_numeric_business_ids'
PROTECTED_TABLES = (
    'sys_user',
    'sys_role',
    'sys_menu',
    'sys_user_role',
    'sys_role_menu',
    'sys_config',
    'sys_dict_type',
    'sys_dict_data',
    'sys_logininfor',
    'sys_oper_log',
    'sys_job',
    'sys_job_log',
    'apscheduler_jobs',
    'alembic_version',
)
TABLE_COUNT = 29
REHEARSAL_PORT = 19432


def row_fingerprints(connection: sa.Connection, tables: list[str]) -> dict:
    result = {}
    for name in tables:
        if not name.replace('_', '').isalnum():
            raise ValueError('Unexpected table')
        result[name] = list(
            connection.execute(
                sa.text(
                    "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
                    f'(SELECT md5(row_to_json(t)::text) h FROM public."{name}" t)s'
                )
            ).one()
        )
    return result


def table_owners(connection: sa.Connection) -> list:
    return [
        list(row)
        for row in connection.execute(
            sa.text("""
        SELECT c.oid,c.relname,c.relowner,c.relacl::text FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.oid
    """)
        )
    ]


def framework_objects(connection: sa.Connection) -> dict:
    """Views and all sequence definitions/counters must survive unchanged."""
    views = [
        list(row)
        for row in connection.execute(
            sa.text("SELECT viewname,definition FROM pg_views WHERE schemaname='public' ORDER BY viewname")
        )
    ]
    sequences = [
        list(row)
        for row in connection.execute(
            sa.text(
                'SELECT sequencename,sequenceowner,data_type::text,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value '
                "FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename"
            )
        )
    ]
    return {'views': views, 'sequences': sequences}


def archive(path: Path, data: dict) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        stream.flush()
        os.fsync(stream.fileno())


# Keep backup checks, protected snapshots, DDL and verification in one savepoint.
def migrate_business_consistency(connection: sa.Connection, *, backup_dir: Path, allow_live: bool = False) -> dict:  # noqa: PLR0912, PLR0915
    """Caller-owned transaction and savepoint; any failed invariant rolls back."""
    if not connection.in_transaction() or connection.dialect.name != 'postgresql':
        raise RuntimeError('A PostgreSQL caller-owned transaction is required')
    url = connection.engine.url
    if allow_live:
        if url.database != 'pipesight':
            raise RuntimeError('Live migration is scoped to pipesight')
    elif url.host not in {'localhost', '127.0.0.1'} or url.port != REHEARSAL_PORT:
        raise RuntimeError('Pass explicit business_allow_live=true for the source database')
    root = backup_dir.resolve()
    if not root.is_dir() or root.stat().st_mode & 0o077:
        raise RuntimeError('A private backup directory is required')
    manifest = json.loads((root / 'database-before.json').read_text())
    if manifest['revision'] != PREVIOUS_REVISION:
        raise RuntimeError('Unexpected backup source revision')
    if hashlib.sha256((root / 'database-before.dump').read_bytes()).hexdigest() != manifest['sha256']:
        raise RuntimeError('Backup SHA-256 mismatch')
    frozen = load_frozen('v4')
    with connection.begin_nested():
        connection.exec_driver_sql("SET LOCAL lock_timeout='5s'")
        connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
        connection.exec_driver_sql('SET LOCAL search_path=public,pg_catalog')
        connection.exec_driver_sql('SELECT pg_advisory_xact_lock(1042026,251025)')
        connection.exec_driver_sql(
            'LOCK TABLE '
            + ','.join('public.' + quote_identifier(n) for n in BUSINESS_TABLES)
            + ' IN ACCESS EXCLUSIVE MODE'
        )
        tables = sorted(sa.inspect(connection).get_table_names(schema='public'))
        if len(tables) != TABLE_COUNT or tables != sorted(manifest['tables']):
            raise RuntimeError('Unexpected physical table inventory')
        if connection.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() != PREVIOUS_REVISION:
            raise RuntimeError('Unexpected live source revision')
        before_rows = row_fingerprints(connection, tables)
        if before_rows != manifest['fingerprints']:
            raise RuntimeError('Source data changed after backup; take a fresh stopped-write backup')
        before = catalog(connection)
        protected = catalog(connection, PROTECTED_TABLES)
        owners = table_owners(connection)
        objects = framework_objects(connection)
        sequence = list(connection.exec_driver_sql('SELECT last_value,is_called FROM public.business_id_seq').one())
        target = frozen['catalog']
        for name in BUSINESS_TABLES:
            current, desired = before[name], target[name]
            current_columns = [(c['name'], c['type'], c['nullable'], c['identity']) for c in current['columns']]
            desired_columns = [(c['name'], c['type'], c['nullable'], c['identity']) for c in desired['columns']]
            if current_columns != desired_columns:
                raise RuntimeError('This migration cannot change field types, nullability or identity: ' + name)
            for kind in ('primary_key', 'foreign_keys', 'unique'):
                if current[kind] != desired[kind]:
                    raise RuntimeError('Unexpected relation or key change: ' + name + ':' + kind)
            for check in frozen['model_ddl'][name]['checks']:
                try:
                    invalid = connection.execute(
                        sa.text(
                            f'SELECT count(*) FROM public.{quote_identifier(name)} WHERE ({check["expression"]}) IS FALSE'
                        )
                    ).scalar_one()
                except sa.exc.DBAPIError as exc:
                    raise RuntimeError(
                        'Existing rows do not satisfy target CHECK: ' + name + '.' + check['name']
                    ) from exc
                if invalid:
                    raise RuntimeError(
                        'Existing rows violate target CHECK; no rows modified: ' + name + '.' + check['name']
                    )
        archive(
            root / 'business-schema-before.json',
            {
                'catalog': before,
                'protected': protected,
                'owners': owners,
                'framework_objects': objects,
                'rows': before_rows,
                'business_sequence': sequence,
                'frozen_sha256': hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest(),
            },
        )
        for name in BUSINESS_TABLES:
            for check in before[name]['checks']:
                connection.exec_driver_sql(
                    f'ALTER TABLE public.{quote_identifier(name)} DROP CONSTRAINT {quote_identifier(check["name"])}'
                )
            for check in frozen['model_ddl'][name]['checks']:
                connection.exec_driver_sql(check['ddl'])
            defaults = {c['name']: c for c in frozen['model_ddl'][name]['columns']}
            for column in before[name]['columns']:
                expected = next(c for c in target[name]['columns'] if c['name'] == column['name'])
                if column['default'] == expected['default'] or column['identity']:
                    continue
                default = defaults[column['name']]['default']
                action = 'DROP DEFAULT' if default is None else 'SET DEFAULT ' + default
                connection.exec_driver_sql(
                    f'ALTER TABLE public.{quote_identifier(name)} ALTER COLUMN {quote_identifier(column["name"])} {action}'
                )
            actual_indexes = {i['name']: i for i in canonical_catalog({name: before[name]})[name]['indexes']}
            desired_indexes = {i['name']: i for i in canonical_catalog({name: target[name]})[name]['indexes']}
            definitions = {i['name']: i['ddl'] for i in frozen['model_ddl'][name]['indexes']}
            for key, actual in actual_indexes.items():
                if actual != desired_indexes.get(key):
                    connection.exec_driver_sql('DROP INDEX public.' + quote_identifier(key))
            for key, desired in desired_indexes.items():
                if desired != actual_indexes.get(key):
                    connection.exec_driver_sql(definitions[key])
            table_comment = target[name]['comment'].replace("'", "''")
            connection.exec_driver_sql(f"COMMENT ON TABLE public.{quote_identifier(name)} IS '{table_comment}'")
            for column in target[name]['columns']:
                comment = column['comment'].replace("'", "''")
                connection.exec_driver_sql(
                    f"COMMENT ON COLUMN public.{quote_identifier(name)}.{quote_identifier(column['name'])} IS '{comment}'"
                )
        after = catalog(connection)
        differences = schema_differences(after, target)
        if differences:
            archive(
                root / 'business-schema-verification-failed.json',
                {'differences': differences, 'actual': after, 'expected': target},
            )
            raise RuntimeError('Frozen business schema mismatch: ' + ', '.join(differences))
        if catalog(connection, PROTECTED_TABLES) != protected or table_owners(connection) != owners:
            raise RuntimeError('Protected foundation metadata or table ownership changed')
        if framework_objects(connection) != objects:
            raise RuntimeError('A directory view or existing sequence changed')
        if row_fingerprints(connection, tables) != before_rows:
            raise RuntimeError('Metadata-only migration unexpectedly changed data')
        if (
            list(connection.exec_driver_sql('SELECT last_value,is_called FROM public.business_id_seq').one())
            != sequence
        ):
            raise RuntimeError('Business sequence state changed')
        result = {
            'tables': TABLE_COUNT,
            'business_tables': len(BUSINESS_TABLES),
            'columns': 340,
            'foreign_keys': 35,
            'data_preserved': True,
            'foundation_preserved': True,
            'business_sequence_preserved': True,
            'catalog_differences': [],
        }
        archive(root / 'business-schema-verification.json', result)
        return result
