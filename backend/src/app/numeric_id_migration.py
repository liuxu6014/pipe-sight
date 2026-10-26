"""Backup-gated numeric business IDs, explicit references and atomic PG DDL."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy as sa

from app.business_ids import BUSINESS_ID_TABLES, MAX_BIGINT, generation_request_fingerprint
from app.schema_comments import COLUMN_COMMENTS, TABLE_COMMENTS

if TYPE_CHECKING:
    from collections.abc import Iterable

REHEARSAL_PORT = 19432
EXPECTED_TABLE_COUNT = 29

JSON_COLUMNS = {
    'collection_runs': ('config_snapshot',),
    'generation_tasks': ('materials', 'config_snapshot'),
    'report_assets': ('config_snapshot',),
    'report_versions': ('sections', 'citations', 'model_snapshot'),
    'digest_schedules': ('selection_config', 'generation_config'),
    'templates': ('sections', 'image_config'),
}
REFERENCE_KEYS = {
    'article_id': 'news_articles',
    'articleId': 'news_articles',
    'paper_id': 'papers',
    'paperId': 'papers',
    'file_id': 'knowledge_files',
    'fileId': 'knowledge_files',
    'material_id': 'knowledge_files',
    'materialId': 'knowledge_files',
    'source_id': 'data_sources',
    'sourceId': 'data_sources',
    'category_id': 'categories',
    'categoryId': 'categories',
    'template_id': 'templates',
    'templateId': 'templates',
    'template_key': 'templates',
    'templateKey': 'templates',
    'report_id': 'reports',
    'reportId': 'reports',
    'task_id': 'generation_tasks',
    'taskId': 'generation_tasks',
    'job_id': 'generation_tasks',
    'jobId': 'generation_tasks',
    'schedule_id': 'digest_schedules',
    'scheduleId': 'digest_schedules',
    'asset_id': 'report_assets',
    'assetId': 'report_assets',
    'export_id': 'report_assets',
    'exportId': 'report_assets',
}
LIST_KEYS = {
    'article_ids': 'news_articles',
    'articleIds': 'news_articles',
    'paper_ids': 'papers',
    'paperIds': 'papers',
    'file_ids': 'knowledge_files',
    'fileIds': 'knowledge_files',
    'category_ids': 'categories',
    'categoryIds': 'categories',
    'source_ids': 'data_sources',
    'sourceIds': 'data_sources',
    'report_ids': 'reports',
    'reportIds': 'reports',
}
KINDS = {
    'article': 'news_articles',
    'news': 'news_articles',
    'wechat': 'news_articles',
    'paper': 'papers',
    'file': 'knowledge_files',
    'document': 'knowledge_files',
    'report': 'reports',
    'template': 'templates',
    'source': 'data_sources',
    'category': 'categories',
    'task': 'generation_tasks',
    'job': 'generation_tasks',
    'schedule': 'digest_schedules',
    'asset': 'report_assets',
}
OPAQUE_KEYS = {
    'content',
    'content_zh',
    'abstract',
    'abstract_zh',
    'prompt',
    'system_prompt',
    'user_prompt',
    'title',
    'name',
    'url',
    'doi',
    'storage_key',
    'storageKey',
    'filename',
    'request_id',
    'requestId',
    'execution_token',
    'executionToken',
    'credential_ref',
    'parameters',
    'model',
    'image_model',
    'model_snapshot',
    'config',
    'checkpoint',
}


def _q(value: str) -> str:
    if not re.fullmatch(r'[a-z_][a-z_0-9]*', value):
        raise ValueError('Unexpected database identifier')
    return '"' + value + '"'


def _json(value: object) -> str:
    def encode(item: object) -> str | dict[str, str]:
        if isinstance(item, datetime):
            return item.astimezone(timezone.utc).isoformat() if item.tzinfo else item.isoformat()
        if isinstance(item, date):
            return item.isoformat()
        if isinstance(item, time):
            return item.isoformat()
        if isinstance(item, (bytes, memoryview)):
            return {'bytes_base64': base64.b64encode(item).decode()}
        raise TypeError(type(item).__name__)

    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=encode, separators=(',', ':'))


def fingerprint(rows: Iterable[dict[str, object]]) -> str:
    return hashlib.sha256(_json(sorted(_json(row) for row in rows)).encode()).hexdigest()


@dataclass
class NumericPlan:
    mappings: dict[str, dict[str, int]]
    target_rows: dict[str, list[dict[str, object]]]
    convert_columns: dict[tuple[str, str], str]
    rewrites: list[dict[str, str | int]]


# Keep projection and validation together so no partial rewrite plan can escape.
def build_plan(  # noqa: PLR0912, PLR0915
    rows: dict[str, list[dict[str, object]]], foreign_keys: list[dict[str, object]]
) -> NumericPlan:
    """Only PKs, real FKs and explicitly structural JSON references may change."""
    mappings, number = {}, 0
    for table in BUSINESS_ID_TABLES:
        keys = [str(row['id']) for row in rows[table]]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate source IDs: ' + table)
        mappings[table] = {}
        for old in sorted(keys):
            number += 1
            if number > MAX_BIGINT:
                raise ValueError('Numeric ID capacity exhausted')
            mappings[table][old] = number
    columns = {(name, 'id'): name for name in BUSINESS_ID_TABLES}
    changed = True
    while changed:
        changed = False
        for fk in foreign_keys:
            for column, referred in zip(fk['columns'], fk['target_columns'], strict=True):
                root = columns.get((fk['target'], referred))
                if root is None:
                    continue
                key = (fk['table'], column)
                if key in columns and columns[key] != root:
                    raise ValueError('Conflicting numeric FK roles')
                if key not in columns:
                    columns[key] = root
                    changed = True
    target, rewrites = deepcopy(rows), []

    def ref(entity: str, value: object, path: str, *, wire: bool = False) -> object:
        if value is None or value == '':
            return value
        if str(value) not in mappings[entity]:
            raise ValueError(f'Unmapped structural reference at {path}: {entity}')
        new = mappings[entity][str(value)]
        rewrites.append({'path': path, 'entity': entity, 'old_id': str(value), 'new_id': new})
        return str(new) if wire else new

    def content_ref(value: object, path: str, kind: str | None = None) -> object:
        entities = [KINDS[kind]] if kind in KINDS else ['news_articles', 'papers', 'knowledge_files', 'reports']
        matches = [entity for entity in entities if str(value) in mappings[entity]]
        if len(matches) != 1:
            raise ValueError('Unmapped or ambiguous selection at ' + path)
        return ref(matches[0], value, path, wire=True)

    # One explicit precedence chain keeps opaque fields ahead of structural IDs.
    def walk(value: object, path: str, context: str | None = None, *, custom: bool = False) -> object:
        if isinstance(value, list):
            return [walk(item, f'{path}[{index}]', context, custom=custom) for index, item in enumerate(value)]
        if not isinstance(value, dict):
            return value
        output = {}
        kind = value.get('type') or value.get('kind') or value.get('sourceType')
        identity_entity = (
            KINDS.get(kind) if context in {'materials', 'items', 'sources', 'evidence', 'selected_items'} else None
        )
        identity_entity = {
            'template': 'templates',
            'source': 'data_sources',
            'report': 'reports',
            'schedule': 'digest_schedules',
            'asset': 'report_assets',
        }.get(context, identity_entity)
        for key, item in value.items():
            child = path + '.' + key
            if key in OPAQUE_KEYS:
                output[key] = item
            elif key == 'id' and identity_entity:
                output[key] = ref(identity_entity, item, child, wire=True)
            elif (key in {'itemId', 'item_id', 'sourceItemId', 'source_item_id'} and item is not None) or (
                key in {'source_id', 'sourceId'}
                and context == 'citations'
                and kind in {'article', 'news', 'wechat', 'paper', 'file', 'document', 'report'}
            ):
                output[key] = content_ref(item, child, kind)
            elif key in {'selected_item_ids', 'selectedItemIds', 'itemIds', 'item_ids'} and isinstance(item, list):
                output[key] = [
                    walk(identity, f'{child}[{index}]', 'materials')
                    if isinstance(identity, dict)
                    else content_ref(identity, f'{child}[{index}]')
                    for index, identity in enumerate(item)
                ]
            elif key in LIST_KEYS and isinstance(item, list):
                output[key] = [
                    ref(LIST_KEYS[key], identity, f'{child}[{index}]', wire=True) for index, identity in enumerate(item)
                ]
            elif key in REFERENCE_KEYS and not isinstance(item, (dict, list)):
                entity = REFERENCE_KEYS[key]
                if custom and item is not None and str(item) not in mappings[entity]:
                    output[key] = item  # External crawler parameters are not platform IDs.
                else:
                    output[key] = ref(entity, item, child, wire=True)
            else:
                output[key] = walk(item, child, key, custom=custom)
        return output

    for table, records in target.items():
        for index, row in enumerate(records):
            for (owner, column), entity in columns.items():
                if owner == table:
                    row[column] = ref(entity, row[column], f'{table}[{index}].{column}')
            for column in JSON_COLUMNS.get(table, ()):
                if row.get(column) is not None:
                    row[column] = walk(
                        row[column], f'{table}[{index}].{column}', column, custom=table in {'data_sources', 'templates'}
                    )
            # Random client keys/tokens stay opaque. System-generated schedule
            # and retry keys contain an actual FK and must follow its mapping.
            before = rows[table][index]
            key = before.get('request_id')
            if table == 'generation_tasks' and before.get('schedule_id') is not None and isinstance(key, str):
                prefix = f'schedule:{before["schedule_id"]}:'
                if key.startswith(prefix):
                    row['request_id'] = f'schedule:{row["schedule_id"]}:' + key[len(prefix) :]
            elif table == 'collection_runs' and isinstance(key, str):
                prefix = f'schedule:{before["source_id"]}:'
                if before.get('trigger_type') == 'schedule' and key.startswith(prefix):
                    row['request_id'] = f'schedule:{row["source_id"]}:' + key[len(prefix) :]
                elif (
                    before.get('trigger_type') == 'retry'
                    and before.get('parent_id') is not None
                    and key == f'retry:{before["parent_id"]}'
                ):
                    row['request_id'] = f'retry:{row["parent_id"]}'
            if table == 'generation_tasks':
                snapshot, original = row.get('config_snapshot') or {}, before.get('config_snapshot') or {}
                digest = original.get('request_fingerprint')
                if (
                    isinstance(digest, str)
                    and re.fullmatch('[a-f0-9]{64}', digest)
                    and isinstance(snapshot.get('request'), dict)
                ):
                    snapshot['request_fingerprint'] = generation_request_fingerprint(
                        snapshot['request'], row.get('materials') or []
                    )
    for table in ('generation_tasks', 'collection_runs'):
        keys = [row['request_id'] for row in target[table] if row.get('request_id') is not None]
        if len(keys) != len(set(keys)):
            raise ValueError('Mapped system idempotency keys collide: ' + table)
    return NumericPlan(mappings, target, columns, rewrites)


def _inventory(bind: sa.Connection) -> set[str]:
    return set(bind.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())


def _rows(bind: sa.Connection, tables: Iterable[str], *, phase: str = 'source') -> dict[str, list[dict[str, object]]]:
    # A SELECT * prepared before ALTER TYPE has a different result descriptor.
    # Use a distinct statement after DDL instead of reusing asyncpg's old plan.
    if phase not in {'source', 'target'}:
        raise ValueError('Unexpected verification phase')
    return {
        table: [
            dict(row)
            for row in bind.execute(sa.text(f'SELECT /* numeric_{phase} */ * FROM public.{_q(table)}')).mappings()
        ]
        for table in sorted(tables)
    }


def _constraints(bind: sa.Connection) -> list[dict[str, object]]:
    return [
        dict(row)
        for row in bind.execute(
            sa.text("""
        SELECT r.relname AS table_name,c.conname AS name,c.contype::text AS type,
               pg_get_constraintdef(c.oid,true) AS definition,c.convalidated AS validated
        FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname='public' ORDER BY r.relname,c.conname
    """)
        ).mappings()
    ]


def _owners(bind: sa.Connection) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in bind.execute(
            sa.text("""
        SELECT c.oid,c.relname,c.relowner,c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.oid
    """)
        )
    ]


def _indexes(bind: sa.Connection) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in bind.execute(
            sa.text("""
        SELECT t.relname,c.relname,pg_get_indexdef(i.indexrelid),i.indisunique,i.indisvalid
        FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_class c ON c.oid=i.indexrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' ORDER BY t.relname,c.relname
    """)
        )
    ]


def _quoted_end(sql: str, start: int) -> int:
    quote = sql[start]
    position = start + 1
    while position < len(sql):
        if sql[position] == quote:
            if position + 1 < len(sql) and sql[position + 1] == quote:
                position += 2
                continue
            return position + 1
        position += 1
    return len(sql)


def _paren_end(sql: str, start: int) -> int | None:
    depth, position = 0, start
    while position < len(sql):
        if sql[position] in '\'"':
            position = _quoted_end(sql, position)
            continue
        if sql[position] == '(':
            depth += 1
        elif sql[position] == ')':
            depth -= 1
            if not depth:
                return position + 1
        position += 1
    return None


def _strip_parens(value: str) -> str:
    value = value.strip()
    while value.startswith('(') and _paren_end(value, 0) == len(value):
        value = value[1:-1].strip()
    return value


def _text_literal_array(value: str) -> str | None:
    value = _strip_parens(value)
    array_cast = value.endswith('::text[]')
    if array_cast:
        value = _strip_parens(value[:-8])
    if not value.startswith('ARRAY[') or not value.endswith(']'):
        return None
    body = value[6:-1]
    parts, start, position, depth = [], 0, 0, 0
    while position < len(body):
        if body[position] in '\'"':
            position = _quoted_end(body, position)
            continue
        if body[position] == '(':
            depth += 1
        elif body[position] == ')':
            depth -= 1
        elif body[position] == ',' and not depth:
            parts.append(body[start:position])
            start = position + 1
        position += 1
    parts.append(body[start:])
    literals = []
    for raw_part in parts:
        part = _strip_parens(raw_part)
        text_cast = False
        while match := re.search(r'::(text|character varying)\s*$', part):
            text_cast |= match.group(1) == 'text'
            part = _strip_parens(part[: match.start()])
        if not (array_cast or text_cast) or not re.fullmatch(r"'(?:[^']|'')*'", part):
            return None
        literals.append(part)
    return 'ARRAY[' + ', '.join(literals) + ']::text[]'


def canonical_catalog_sql(sql: str) -> str:
    """Normalize only equivalent literal text arrays emitted by PG 18 deparsers."""
    output, position = [], 0
    while position < len(sql):
        if sql[position] == '$' and (delimiter := re.match(r'\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$', sql[position:])):
            marker = delimiter.group(0)
            closing = sql.find(marker, position + len(marker))
            end = closing + len(marker) if closing >= 0 else len(sql)
            output.append(sql[position:end])
            position = end
            continue
        if sql[position] in '\'"':
            end = _quoted_end(sql, position)
            output.append(sql[position:end])
            position = end
            continue
        match = re.match(r'(ANY|ALL)\s*\(', sql[position:])
        if match and (not position or not (sql[position - 1].isalnum() or sql[position - 1] == '_')):
            opening = position + match.end() - 1
            end = _paren_end(sql, opening)
            array = _text_literal_array(sql[opening + 1 : end - 1]) if end else None
            if array is not None:
                output.append(match.group(1) + ' (' + array + ')')
                position = end
                continue
        output.append(sql[position])
        position += 1
    return ''.join(output)


def _constraint_signature(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return [{**row, 'definition': canonical_catalog_sql(row['definition'])} for row in rows]


def _index_signature(rows: Iterable[tuple[object, ...]]) -> list[tuple[object, ...]]:
    return [
        (table, name, canonical_catalog_sql(definition), unique, valid)
        for table, name, definition, unique, valid in rows
    ]


def _archive(plan: NumericPlan, root: Path, source_rows: dict[str, list[dict[str, object]]]) -> None:
    path = root / 'numeric-id-mapping.json'
    payload = {
        'mappings': plan.mappings,
        'reference_rewrites': plan.rewrites,
        'source_fingerprints': {table: fingerprint(rows) for table, rows in source_rows.items()},
        'target_fingerprints': {table: fingerprint(rows) for table, rows in plan.target_rows.items()},
    }
    encoded = _json(payload).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(encoded)
        output.flush()
        os.fsync(output.fileno())
    if path.read_bytes() != encoded:
        raise RuntimeError('ID mapping archive verification failed')


# Preserve a single savepoint for backup checks, DDL, row and catalog verification.
def migrate_numeric_ids(  # noqa: PLR0912, PLR0915
    bind: sa.Connection, *, manifest: dict[str, object], backup_dir: str | Path, allow_live: bool = False
) -> dict[str, int | bool]:
    if not bind.in_transaction():
        raise RuntimeError('A caller-owned transaction is required')
    url = bind.engine.url
    if allow_live:
        if url.database != 'pipesight':
            raise RuntimeError('Live numeric migration is scoped to pipesight')
    elif not (url.host in {'127.0.0.1', 'localhost'} and url.port == REHEARSAL_PORT):
        raise RuntimeError('Live migration requires explicit numeric_allow_live=true')
    root = Path(backup_dir).resolve()
    if not root.is_dir() or root.stat().st_mode & 0o077:
        raise RuntimeError('Backup directory must be private')
    if manifest['revision'] != '20261025_restore_ruoyi_names':
        raise RuntimeError('Unexpected source revision')
    if hashlib.sha256((root / 'database-before.dump').read_bytes()).hexdigest() != manifest['sha256']:
        raise RuntimeError('Backup dump SHA-256 mismatch')
    tables = set(TABLE_COMMENTS)
    if len(tables) != EXPECTED_TABLE_COUNT or set(manifest['tables']) != tables:
        raise RuntimeError('Unexpected source table contract')
    with bind.begin_nested():
        bind.exec_driver_sql("SET LOCAL lock_timeout='5s'")
        bind.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
        bind.exec_driver_sql('SELECT pg_advisory_xact_lock(20261025, 30)')
        if _inventory(bind) != tables:
            raise RuntimeError('Unexpected source tables')
        bind.exec_driver_sql(
            'LOCK TABLE ' + ','.join('public.' + _q(name) for name in sorted(tables)) + ' IN ACCESS EXCLUSIVE MODE'
        )
        for table in tables:
            actual = list(
                bind.execute(
                    sa.text(
                        "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
                        f'(SELECT md5(row_to_json(t)::text) h FROM public.{_q(table)} t)s'
                    )
                ).one()
            )
            if actual != manifest['fingerprints'][table]:
                raise RuntimeError('Source changed since backup: ' + table)
        if bind.scalar(sa.text("SELECT to_regclass('public.business_id_seq')")) is not None:
            raise RuntimeError('Numeric sequence already exists; refuse partial migration')
        inspector = sa.inspect(bind)
        columns = {
            table: {column['name']: column for column in inspector.get_columns(table, schema='public')}
            for table in tables
        }
        foreign_keys = []
        definitions = _constraints(bind)
        if not all(row['validated'] for row in definitions):
            raise RuntimeError('Unvalidated source constraints')
        for table in tables:
            for fk in inspector.get_foreign_keys(table, schema='public'):
                if fk.get('referred_schema') not in (None, 'public'):
                    raise RuntimeError('Cross-schema FK needs explicit review')
                foreign_keys.append(
                    {
                        'table': table,
                        'columns': fk['constrained_columns'],
                        'target': fk['referred_table'],
                        'target_columns': fk['referred_columns'],
                        'name': fk['name'],
                    }
                )
        source = _rows(bind, tables)
        plan = build_plan(source, foreign_keys)
        owners = _owners(bind)
        indexes = _indexes(bind)
        for table, column in plan.convert_columns:
            metadata = columns[table][column]
            if not isinstance(metadata['type'], sa.String) or metadata.get('default') is not None:
                raise RuntimeError(f'Unexpected source ID type/default: {table}.{column}')
        _archive(plan, root, source)
        bind.exec_driver_sql(
            'CREATE TEMP TABLE numeric_id_map(entity text NOT NULL,old_id text NOT NULL,new_id bigint NOT NULL UNIQUE,PRIMARY KEY(entity,old_id)) ON COMMIT DROP'
        )
        entries = [
            {'entity': table, 'old_id': old, 'new_id': new}
            for table, mapping in plan.mappings.items()
            for old, new in mapping.items()
        ]
        if entries:
            bind.execute(
                sa.text('INSERT INTO pg_temp.numeric_id_map(entity,old_id,new_id) VALUES(:entity,:old_id,:new_id)'),
                entries,
            )
        bind.exec_driver_sql("""CREATE FUNCTION pg_temp.numeric_ref(entity text,value text) RETURNS bigint LANGUAGE SQL STRICT STABLE
            AS 'SELECT new_id FROM pg_temp.numeric_id_map m WHERE m.entity=$1 AND m.old_id=$2'""")
        affected = {
            (fk['table'], fk['name'])
            for fk in foreign_keys
            if any((fk['table'], column) in plan.convert_columns for column in fk['columns'])
            or any((fk['target'], column) in plan.convert_columns for column in fk['target_columns'])
        }
        for table, name in sorted(affected):
            bind.exec_driver_sql(f'ALTER TABLE public.{_q(table)} DROP CONSTRAINT {_q(name)} RESTRICT')
        for (table, column), entity in sorted(plan.convert_columns.items()):
            bind.exec_driver_sql(
                f"ALTER TABLE public.{_q(table)} ALTER COLUMN {_q(column)} TYPE bigint USING pg_temp.numeric_ref('{entity}',{_q(column)}::text)"
            )
        # Move rewritten unique system keys out of the way before assigning
        # their final values (old/new keys may otherwise form a permutation).
        for table in ('generation_tasks', 'collection_runs'):
            for before, row in zip(source[table], plan.target_rows[table], strict=True):
                if before.get('request_id') != row.get('request_id'):
                    temporary = (
                        'numeric-migration:'
                        + hashlib.sha256((table + str(row['id']) + manifest['sha256']).encode()).hexdigest()
                    )
                    bind.execute(
                        sa.text(f'UPDATE public.{_q(table)} SET request_id=:key WHERE id=:id'),
                        {'key': temporary, 'id': row['id']},
                    )
        reverse_mappings = {
            table: {new: old for old, new in mapping.items()} for table, mapping in plan.mappings.items()
        }
        for table, json_columns in JSON_COLUMNS.items():
            before_by_id = {str(row['id']): row for row in source[table]}
            for row in plan.target_rows[table]:
                old_id = reverse_mappings.get(table, {}).get(row['id'], str(row['id']))
                before = before_by_id[old_id]
                for column in json_columns:
                    if row.get(column) != before.get(column):
                        bind.execute(
                            sa.text(f'UPDATE public.{_q(table)} SET {_q(column)}=CAST(:value AS jsonb) WHERE id=:id'),
                            {'value': json.dumps(row[column], ensure_ascii=False), 'id': row['id']},
                        )
                if table in {'generation_tasks', 'collection_runs'} and row.get('request_id') != before.get(
                    'request_id'
                ):
                    bind.execute(
                        sa.text(f'UPDATE public.{_q(table)} SET request_id=:key WHERE id=:id'),
                        {'key': row['request_id'], 'id': row['id']},
                    )
        for constraint in definitions:
            if (constraint['table_name'], constraint['name']) in affected:
                bind.exec_driver_sql(
                    f'ALTER TABLE public.{_q(constraint["table_name"])} ADD CONSTRAINT {_q(constraint["name"])} {constraint["definition"]}'
                )
        bind.exec_driver_sql('CREATE SEQUENCE public.business_id_seq AS bigint MINVALUE 1 NO CYCLE')
        maximum = max((new for mapping in plan.mappings.values() for new in mapping.values()), default=0)
        bind.execute(
            sa.text("SELECT setval('public.business_id_seq',:value,:called)"),
            {'value': max(maximum, 1), 'called': maximum > 0},
        )
        for table in BUSINESS_ID_TABLES:
            bind.exec_driver_sql(
                f"ALTER TABLE public.{_q(table)} ALTER COLUMN id SET DEFAULT nextval('public.business_id_seq'::regclass)"
            )
        actual_rows = _rows(bind, tables, phase='target')
        for table in tables:
            if fingerprint(actual_rows[table]) != fingerprint(plan.target_rows[table]):
                raise RuntimeError('Target rows differ from numeric projection: ' + table)
        after_constraints, after_indexes = _constraints(bind), _indexes(bind)
        if (
            _owners(bind) != owners
            or _constraint_signature(after_constraints) != _constraint_signature(definitions)
            or _index_signature(after_indexes) != _index_signature(indexes)
            or _inventory(bind) != tables
        ):
            diagnostic = root / 'numeric-metadata-verification-failure.json'
            fd = os.open(diagnostic, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as output:
                output.write(
                    _json(
                        {
                            'constraints_before': definitions,
                            'constraints_after': after_constraints,
                            'indexes_before': indexes,
                            'indexes_after': after_indexes,
                            'owners_before': owners,
                            'owners_after': _owners(bind),
                            'tables_before': sorted(tables),
                            'tables_after': sorted(_inventory(bind)),
                        }
                    )
                )
            raise RuntimeError('Table identity, ownership, ACL or constraint semantics changed')
        inspector = sa.inspect(bind)
        for table in tables:
            target_columns = inspector.get_columns(table, schema='public')
            if {column['name'] for column in target_columns} != set(columns[table]):
                raise RuntimeError('Column set changed')
            for column in target_columns:
                old = columns[table][column['name']]
                converted = (table, column['name']) in plan.convert_columns
                if converted and not isinstance(column['type'], sa.BigInteger):
                    raise RuntimeError('ID column is not bigint')
                if not converted and str(column['type']) != str(old['type']):
                    raise RuntimeError('Unrelated column type changed')
                if column['nullable'] != old['nullable']:
                    raise RuntimeError('Column nullability changed')
                if table in BUSINESS_ID_TABLES and column['name'] == 'id':
                    if 'business_id_seq' not in str(column.get('default')):
                        raise RuntimeError('Business primary key lacks the shared sequence default')
                elif column.get('default') != old.get('default'):
                    raise RuntimeError('Unrelated column default changed')
            comment = TABLE_COMMENTS[table].replace("'", "''")
            bind.exec_driver_sql(f"COMMENT ON TABLE public.{_q(table)} IS '{comment}'")
            for column, raw_comment in COLUMN_COMMENTS[table].items():
                comment = raw_comment.replace("'", "''")
                bind.exec_driver_sql(f"COMMENT ON COLUMN public.{_q(table)}.{_q(column)} IS '{comment}'")
        return {
            'tables': len(tables),
            'numeric_primary_keys': len(BUSINESS_ID_TABLES),
            'converted_columns': len(plan.convert_columns),
            'mapped_records': maximum,
            'json_references_rewritten': len(plan.rewrites),
            'all_projected_rows_verified': True,
        }
