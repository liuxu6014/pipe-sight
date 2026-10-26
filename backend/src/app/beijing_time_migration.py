"""Backup-gated conversion of business audit clocks, never framework timestamps."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import sqlalchemy as sa

from app.business_schema import BUSINESS_TABLES, catalog, load_frozen, quote_identifier, schema_differences
from app.business_schema_migration import (
    PROTECTED_TABLES,
    archive,
    framework_objects,
    row_fingerprints,
    table_owners,
)

if TYPE_CHECKING:
    from pathlib import Path

REVISION = '20261025_beijing_audit_time'
PREVIOUS_REVISION = '20261025_business_consistency'
AUDIT_COLUMNS = frozenset({'created_at', 'updated_at'})
REHEARSAL_PORT = 19432
TABLE_COUNT = 29


def audit_columns(frozen: dict) -> dict[str, list[str]]:
    return {
        name: [column['name'] for column in frozen['catalog'][name]['columns'] if column['name'] in AUDIT_COLUMNS]
        for name in BUSINESS_TABLES
    }


def projected_fingerprints(connection: sa.Connection, columns: dict[str, list[str]], *, before: bool) -> dict:
    """Compare every value, allowing only the declared timezone/floor conversion.

    jsonb makes object order independent. SQL NULL is retained as JSON null;
    other datetime fields are never normalized, truncated or rewritten.
    """
    result = {}
    for name, selected in columns.items():
        expression = 'to_jsonb(t)'
        if before and selected:
            pairs = ','.join(
                f"'{field}',date_trunc('second',t.{quote_identifier(field)} AT TIME ZONE 'Asia/Shanghai')"
                for field in selected
            )
            expression += f' || jsonb_build_object({pairs})'
        query = (
            "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
            f'(SELECT md5(({expression})::text) h FROM public.{quote_identifier(name)} t)s'
        )
        result[name] = list(connection.exec_driver_sql(query).one())
    return result


def validate_conversion_scope(previous: dict, target: dict) -> dict[str, list[str]]:  # noqa: PLR0912
    """Fail closed if a future snapshot attempts unrelated metadata changes."""
    selected = audit_columns(previous)
    if set(previous['catalog']) != set(target['catalog']) or set(selected) != set(BUSINESS_TABLES):
        raise RuntimeError('Unexpected business inventory')
    for name in BUSINESS_TABLES:
        old, new = previous['catalog'][name], target['catalog'][name]
        if len(old['columns']) != len(new['columns']):
            raise RuntimeError('This migration cannot add or remove columns')
        for left, right in zip(old['columns'], new['columns'], strict=True):
            if left['name'] not in selected[name]:
                if left != right:
                    raise RuntimeError('Non-audit field changed: ' + name + '.' + left['name'])
                continue
            if left['type'] != 'timestamp with time zone' or right['type'] != 'timestamp(0) without time zone':
                raise RuntimeError('Unexpected audit source or destination type')
            if {k: v for k, v in left.items() if k not in {'type', 'default', 'comment'}} != {
                k: v for k, v in right.items() if k not in {'type', 'default', 'comment'}
            }:
                raise RuntimeError('Audit identity/nullability/comment changed unexpectedly')
        for key in set(old) | set(new):
            if key not in {'columns', 'checks'} and old.get(key) != new.get(key):
                raise RuntimeError('Unrelated relation/index/ownership change: ' + name + ':' + key)
        old_checks = {c['name']: c for c in old['checks']}
        new_checks = {c['name']: c for c in new['checks']}
        if set(old_checks) != set(new_checks):
            raise RuntimeError('This migration cannot add or remove PostgreSQL checks')
        for key, old_check in old_checks.items():
            if old_check != new_checks[key] and (name, key) != ('collection_runs', 'ck_collection_runs_times'):
                raise RuntimeError('Unrelated CHECK change: ' + key)
    return selected


def migrate_beijing_audit_time(connection: sa.Connection, *, backup_dir: Path, allow_live: bool = False) -> dict:  # noqa: PLR0912, PLR0915
    """Atomic, explicit Beijing wall-clock migration under a caller transaction."""
    if not connection.in_transaction() or connection.dialect.name != 'postgresql':
        raise RuntimeError('A PostgreSQL caller-owned transaction is required')
    url = connection.engine.url
    if allow_live:
        if url.database != 'pipesight':
            raise RuntimeError('Live target must be pipesight')
    elif (
        url.host not in {'localhost', '127.0.0.1'}
        or url.port != REHEARSAL_PORT
        or not (url.database or '').startswith('pipesight_beijing_')
    ):
        raise RuntimeError('Explicit beijing_allow_live=true is required for source migration')
    root = backup_dir.resolve()
    if not root.is_dir() or root.stat().st_mode & 0o077:
        raise RuntimeError('A private backup directory is required')
    manifest = json.loads((root / 'database-before.json').read_text())
    if manifest['revision'] != PREVIOUS_REVISION:
        raise RuntimeError('Unexpected backup revision')
    if hashlib.sha256((root / 'database-before.dump').read_bytes()).hexdigest() != manifest['sha256']:
        raise RuntimeError('Backup checksum mismatch')
    previous, target = load_frozen('v4'), load_frozen('v5')
    selected = validate_conversion_scope(previous, target)
    with connection.begin_nested():
        connection.exec_driver_sql("SET LOCAL lock_timeout='5s'")
        connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
        connection.exec_driver_sql('SET LOCAL search_path=public,pg_catalog')
        connection.exec_driver_sql('SELECT pg_advisory_xact_lock(1042026,251026)')
        connection.exec_driver_sql(
            'LOCK TABLE '
            + ','.join('public.' + quote_identifier(n) for n in BUSINESS_TABLES)
            + ' IN ACCESS EXCLUSIVE MODE'
        )
        tables = sorted(sa.inspect(connection).get_table_names(schema='public'))
        if len(tables) != TABLE_COUNT or tables != sorted(manifest['tables']):
            raise RuntimeError('Unexpected table inventory')
        if connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() != PREVIOUS_REVISION:
            raise RuntimeError('Unexpected source revision')
        before_rows = row_fingerprints(connection, tables)
        if before_rows != manifest['fingerprints']:
            raise RuntimeError('Data changed after backup; take a fresh stopped-write backup')
        if schema_differences(catalog(connection), previous['catalog']):
            raise RuntimeError('Source schema does not match frozen v4')
        protected = catalog(connection, PROTECTED_TABLES)
        owners, objects = table_owners(connection), framework_objects(connection)
        expected = projected_fingerprints(connection, selected, before=True)
        archive(
            root / 'beijing-schema-before.json',
            {
                'protected': protected,
                'owners': owners,
                'framework_objects': objects,
                'rows': before_rows,
                'projected_business_rows': expected,
                'audit_columns': selected,
            },
        )
        # Drop the one mixed-aware/naive comparison before changing its input type.
        connection.exec_driver_sql('ALTER TABLE public.collection_runs DROP CONSTRAINT ck_collection_runs_times')
        for name, fields in selected.items():
            definitions = {c['name']: c for c in target['model_ddl'][name]['columns']}
            for field in fields:
                prefix = f'ALTER TABLE public.{quote_identifier(name)} ALTER COLUMN {quote_identifier(field)} '
                connection.exec_driver_sql(prefix + 'DROP DEFAULT')
                connection.exec_driver_sql(
                    prefix + 'TYPE timestamp(0) without time zone USING '
                    f"date_trunc('second',{quote_identifier(field)} AT TIME ZONE 'Asia/Shanghai')"
                )
                default = definitions[field]['default']
                if default is not None:
                    connection.exec_driver_sql(prefix + 'SET DEFAULT ' + default)
                comment = definitions[field]['comment'].replace("'", "''")
                connection.exec_driver_sql(
                    f"COMMENT ON COLUMN public.{quote_identifier(name)}.{quote_identifier(field)} IS '{comment}'"
                )
        check = next(
            c for c in target['model_ddl']['collection_runs']['checks'] if c['name'] == 'ck_collection_runs_times'
        )
        connection.exec_driver_sql(check['ddl'])
        differences = schema_differences(catalog(connection), target['catalog'])
        if differences:
            archive(root / 'beijing-schema-failed.json', {'differences': differences, 'actual': catalog(connection)})
            raise RuntimeError('Target schema mismatch: ' + ', '.join(differences))
        if projected_fingerprints(connection, selected, before=False) != expected:
            raise RuntimeError('Data differs from explicit Beijing/floor-seconds projection')
        if catalog(connection, PROTECTED_TABLES) != protected or table_owners(connection) != owners:
            raise RuntimeError('Protected schema or table ownership changed')
        if framework_objects(connection) != objects:
            raise RuntimeError('Views or sequence definitions/counters changed')
        after_rows = row_fingerprints(connection, tables)
        if any(after_rows[n] != before_rows[n] for n in tables if n not in BUSINESS_TABLES):
            raise RuntimeError('Non-business data changed')
        result = {
            'revision': REVISION,
            'tables': len(tables),
            'business_tables': len(selected),
            'audit_columns': sum(map(len, selected.values())),
            'timezone': 'Asia/Shanghai',
            'precision': 'seconds',
            'business_data': 'exact_expected_projection',
            'protected_tables': 'unchanged',
            'views_sequences_owners': 'unchanged',
            'schema_differences': differences,
        }
        archive(root / 'beijing-migration-verification.json', result)
        return result
