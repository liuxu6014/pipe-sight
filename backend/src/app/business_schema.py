"""Read-only, frozen PostgreSQL business-schema parity checks.

Foundation and framework objects are deliberately excluded from alignment.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateIndex

from app.business_ids import BUSINESS_ID_TABLES
from app.numeric_id_migration import canonical_catalog_sql

BUSINESS_TABLES = (
    'ai_models',
    'basket_items',
    'categories',
    'collection_runs',
    'data_sources',
    'digest_schedules',
    'generation_tasks',
    'knowledge_files',
    'model_calls',
    'news_articles',
    'papers',
    'report_assets',
    'report_versions',
    'reports',
    'templates',
)
FROZEN_PATH = Path(__file__).resolve().parents[2] / 'data/schema/business-v5.json'


def quote_identifier(value: str) -> str:
    if value not in BUSINESS_TABLES and not value.replace('_', '').isalnum():
        raise ValueError('Unexpected SQL identifier')
    return '"' + value.replace('"', '""') + '"'


def model_ddl(metadata: sa.MetaData) -> dict:
    """Freeze PostgreSQL declarations, not a future mutable model import."""
    dialect = postgresql.dialect()
    compiler = dialect.ddl_compiler(dialect, None)
    result = {}
    for name in BUSINESS_TABLES:
        table = metadata.tables[name]
        columns = []
        for column in table.c:
            default = (
                compiler.get_column_default_string(column)
                if isinstance(column.server_default, sa.DefaultClause)
                else None
            )
            columns.append(
                {
                    'name': column.name,
                    'type': column.type.compile(dialect=dialect),
                    'nullable': column.nullable,
                    'primary_key': column.primary_key,
                    'default': default,
                    'identity': str(column.identity) if column.identity is not None else None,
                    'comment': column.comment,
                }
            )
        checks = []
        for constraint in table.constraints:
            if not isinstance(constraint, sa.CheckConstraint):
                continue
            condition = constraint._ddl_if
            if condition is not None and condition.dialect is not None:
                allowed = condition.dialect
                if 'postgresql' not in ((allowed,) if isinstance(allowed, str) else allowed):
                    continue
            if not constraint.name:
                raise ValueError('Every business CHECK must have a frozen explicit name')
            checks.append(
                {
                    'name': constraint.name,
                    'expression': str(constraint.sqltext),
                    'ddl': str(AddConstraint(constraint, isolate_from_table=False).compile(dialect=dialect)),
                }
            )
        indexes = [
            {'name': index.name, 'ddl': str(CreateIndex(index).compile(dialect=dialect))} for index in table.indexes
        ]
        result[name] = {
            'columns': columns,
            'comment': table.comment,
            'checks': sorted(checks, key=lambda v: v['name']),
            'indexes': sorted(indexes, key=lambda v: v['name']),
            'foreign_keys': sorted(
                [
                    {
                        'name': fk.name,
                        'columns': list(fk.columns.keys()),
                        'target_schema': fk.referred_table.schema or 'public',
                        'target': fk.referred_table.name,
                        'target_columns': [e.column.name for e in fk.elements],
                        'ondelete': fk.ondelete or 'NO ACTION',
                        'onupdate': fk.onupdate or 'NO ACTION',
                        'match': fk.match or 'SIMPLE',
                        'deferrable': bool(fk.deferrable),
                        'initially': fk.initially or 'IMMEDIATE',
                    }
                    for fk in table.foreign_key_constraints
                ],
                key=lambda fk: tuple(fk['columns']),
            ),
            'unique': sorted(
                [
                    {
                        'name': constraint.name,
                        'columns': list(constraint.columns.keys()),
                        'deferrable': bool(constraint.deferrable),
                        'initially': constraint.initially or 'IMMEDIATE',
                        'nulls_not_distinct': bool(constraint.dialect_options['postgresql'].get('nulls_not_distinct')),
                    }
                    for constraint in table.constraints
                    if isinstance(constraint, sa.UniqueConstraint)
                ],
                key=lambda c: tuple(c['columns']),
            ),
        }
    return result


# Keep columns, relations and optional sequence metadata in one coherent snapshot.
def catalog(connection: sa.Connection, tables: tuple[str, ...] = BUSINESS_TABLES) -> dict:  # noqa: PLR0912
    """Snapshot actual types, defaults, identity, CHECKs, indexes and relations."""
    selected = set(tables)
    output = {name: {'columns': [], 'checks': [], 'indexes': [], 'foreign_keys': [], 'unique': []} for name in tables}
    for row in connection.execute(
        sa.text("""
        SELECT r.relname AS table_name,a.attname AS name,format_type(a.atttypid,a.atttypmod) AS type,
               NOT a.attnotnull AS nullable,pg_get_expr(d.adbin,d.adrelid) AS default,a.attidentity::text AS identity,
               col_description(r.oid,a.attnum) AS comment
        FROM pg_attribute a JOIN pg_class r ON r.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=r.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=r.oid AND d.adnum=a.attnum
        WHERE n.nspname='public' AND r.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY r.relname,a.attnum
    """)
    ).mappings():
        if row['table_name'] in selected:
            output[row['table_name']]['columns'].append({k: v for k, v in row.items() if k != 'table_name'})
    inspector = sa.inspect(connection)
    fk_properties = {
        (r['table_name'], r['name']): dict(r)
        for r in connection.execute(
            sa.text("""
        SELECT r.relname AS table_name,c.conname AS name,tn.nspname AS target_schema,c.convalidated AS validated
        FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace
        JOIN pg_class t ON t.oid=c.confrelid JOIN pg_namespace tn ON tn.oid=t.relnamespace
        WHERE n.nspname='public' AND c.contype='f'
    """)
        ).mappings()
    }
    shared_sequence = (
        connection.execute(
            sa.text("""
        SELECT data_type::text AS type,start_value,min_value,max_value,increment_by,cycle,cache_size
        FROM pg_sequences WHERE schemaname='public' AND sequencename='business_id_seq'
    """)
        )
        .mappings()
        .first()
    )
    sequence = (
        {k: str(v) if isinstance(v, int) and abs(v) > 2**53 - 1 else v for k, v in shared_sequence.items()}
        if shared_sequence
        else None
    )
    if sequence is not None:
        owned = (
            connection.execute(
                sa.text("""
            SELECT n.nspname||'.'||t.relname||'.'||a.attname
            FROM pg_depend d JOIN pg_class s ON s.oid=d.objid JOIN pg_namespace sn ON sn.oid=s.relnamespace
            JOIN pg_class t ON t.oid=d.refobjid JOIN pg_namespace n ON n.oid=t.relnamespace
            JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=d.refobjsubid
            WHERE sn.nspname='public' AND s.relname='business_id_seq' AND d.deptype IN ('a','i')
        """)
            )
            .scalars()
            .all()
        )
        sequence['owned_by'] = owned
    for name in tables:
        if name in BUSINESS_ID_TABLES:
            output[name]['sequence'] = sequence
        output[name]['comment'] = inspector.get_table_comment(name, schema='public')['text']
        identities = {c['name']: c.get('identity') for c in inspector.get_columns(name, schema='public')}
        for column in output[name]['columns']:
            if column['identity']:
                column['identity_options'] = {
                    k: str(v) if isinstance(v, int) and abs(v) > 2**53 - 1 else v
                    for k, v in identities[column['name']].items()
                }
        for key in ('constrained_columns',):
            output[name]['primary_key'] = inspector.get_pk_constraint(name, schema='public')[key]
        output[name]['unique'] = sorted(
            [sorted(c['column_names']) for c in inspector.get_unique_constraints(name, schema='public')]
        )
        for foreign_key in inspector.get_foreign_keys(name, schema='public'):
            options = foreign_key.get('options', {})
            output[name]['foreign_keys'].append(
                {
                    'columns': foreign_key['constrained_columns'],
                    'target': foreign_key['referred_table'],
                    'target_schema': fk_properties[name, foreign_key['name']]['target_schema'],
                    'validated': fk_properties[name, foreign_key['name']]['validated'],
                    'target_columns': foreign_key['referred_columns'],
                    'ondelete': options.get('ondelete', 'NO ACTION'),
                    'onupdate': options.get('onupdate', 'NO ACTION'),
                    'match': options.get('match', 'SIMPLE'),
                    'deferrable': options.get('deferrable', False),
                    'initially': options.get('initially', 'IMMEDIATE'),
                }
            )
        output[name]['foreign_keys'].sort(key=lambda f: tuple(f['columns']))
    for row in connection.execute(
        sa.text("""
        SELECT r.relname AS table_name,c.conname AS name,pg_get_constraintdef(c.oid,true) AS definition,c.convalidated AS validated
        FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname='public' AND c.contype='c'
        ORDER BY r.relname,c.conname
    """)
    ).mappings():
        if row['table_name'] in selected:
            output[row['table_name']]['checks'].append({k: v for k, v in row.items() if k != 'table_name'})
    for row in connection.execute(
        sa.text("""
        SELECT t.relname AS table_name,c.relname AS name,pg_get_indexdef(i.indexrelid) AS definition,
               i.indisunique AS unique,i.indisvalid AS valid
        FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_class c ON c.oid=i.indexrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname='public' AND NOT i.indisprimary
          AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid=i.indexrelid AND k.contype IN ('p','u'))
        ORDER BY t.relname,c.relname
    """)
    ).mappings():
        if row['table_name'] in selected:
            output[row['table_name']]['indexes'].append({k: v for k, v in row.items() if k != 'table_name'})
    return output


def canonical_catalog(value: dict) -> dict:
    result = json.loads(json.dumps(value))
    for table in result.values():
        for kind in ('checks', 'indexes'):
            for item in table[kind]:
                item['definition'] = canonical_catalog_sql(item['definition'])
    return result


def load_frozen(version: str | None = None) -> dict:
    """Runtime target may advance; a historical migration pins its own version."""
    if version is not None and version not in {'v4', 'v5'}:
        raise ValueError('Unsupported frozen business schema version')
    path = FROZEN_PATH if version is None else FROZEN_PATH.with_name(f'business-{version}.json')
    return json.loads(path.read_text(encoding='utf-8'))


def schema_differences(actual: dict, expected: dict) -> list[str]:
    actual, expected = canonical_catalog(actual), canonical_catalog(expected)
    differences = []
    for name in sorted(set(actual) | set(expected)):
        if name not in actual or name not in expected:
            differences.append(name + ':table')
            continue
        differences.extend(
            name + ':' + kind
            for kind in sorted(set(actual[name]) | set(expected[name]))
            if actual[name].get(kind) != expected[name].get(kind)
        )
    return differences


def validate_business_schema(connection: sa.Connection, metadata: sa.MetaData | None = None) -> None:
    if connection.dialect.name != 'postgresql':
        return
    frozen = load_frozen()
    if metadata is not None and model_ddl(metadata) != frozen['model_ddl']:
        raise RuntimeError('业务模型声明与冻结契约不一致，请同步代码及数据库迁移')
    differences = schema_differences(catalog(connection), frozen['catalog'])
    if differences:
        raise RuntimeError('业务数据库结构与当前冻结契约不一致，请先备份并迁移：' + ', '.join(differences))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
