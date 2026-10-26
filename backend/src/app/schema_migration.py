"""Conservative, transactional compact-v1 migration with explicit rollout gates.

This module deliberately does not import application models or configuration.
Call ``preflight`` without a write transaction to inspect a plan. Before applying,
``archive_plan`` writes a private, verified archive of retired business rows.
``migrate`` re-reads under table locks and rejects a stale archive. The caller
owns the outer transaction (Alembic does this); no helper commits it.

Only the approved sparse legacy dataset is supported. Nonempty unimplemented
entities are prerequisites, never an excuse to discard them. Downgrade requires
restoring the independently verified backup, not synthesising old data.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.schema_comments_v1 import (
    COLUMN_COMMENTS,
    FRAMEWORK_TABLE_NAMES,
    OPTIONAL_TABLE_NAMES,
    TABLE_COMMENTS,
    VIEW_COMMENTS,
)
from app.schema_contract import SchemaPrerequisiteError, load_contract

BASE_TABLES = dict(zip(
    ('users', 'roles', 'menus', 'user_roles', 'role_menus', 'settings',
     'dict_types', 'dict_items', 'login_logs', 'operation_logs',
     'scheduled_jobs', 'job_logs', 'apscheduler_jobs', 'alembic_version'),
    ('sys_user', 'sys_role', 'sys_menu', 'sys_user_role', 'sys_role_menu',
     'sys_config', 'sys_dict_type', 'sys_dict_data', 'sys_logininfor',
     'sys_oper_log', 'sys_job', 'sys_job_log', 'apscheduler_jobs', 'alembic_version'),
    strict=True,
))
REHEARSAL_PORT = 19432
PUBLIC_BUSINESS = (
    'ai_chat_config', 'ai_models', 'collection_runs', 'content_review_events',
    'data_sources', 'digest_schedules', 'duplicate_group_events', 'duplicate_groups',
    'duplicate_members', 'generation_tasks', 'knowledge_files', 'model_calls',
    'model_route_usage', 'model_routes', 'news_articles', 'papers', 'prompt_versions',
    'quality_issue_events', 'quality_issues', 'report_exports', 'report_publications',
    'report_versions', 'reports', 'template_versions', 'user_saved_items',
)
NEWS_TABLES = ('articles', 'data_sources', 'domain_topic_rules', 'domains',
               'embeddings', 'prompt_usages', 'prompt_versions', 'topics')
SOURCE_TABLES = ({f'public.{n}' for n in BASE_TABLES.values()} |
                 {f'public.{n}' for n in PUBLIC_BUSINESS} |
                 {f'news.{n}' for n in NEWS_TABLES})
OPTIONAL_TABLES = ('model_calls', 'report_versions')
MAPPED = {'public.news_articles', 'public.papers', 'news.domains',
          'public.prompt_versions', 'public.template_versions', 'public.user_saved_items',
          'public.content_review_events'}
CONTRACT_SHA256 = 'b476a7cb7b9366c6f139ea2fc8318826db5c9d5c8e4402e8884b0cc753170b51'


def normalise_optional_tables(values: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(values, (str, bool)) or len(values) != len(set(values)) or set(values) - set(OPTIONAL_TABLE_NAMES):
        raise SchemaPrerequisiteError('Optional tables must be an exact approved set; personal chat is retired')
    return tuple(name for name in OPTIONAL_TABLE_NAMES if name in values)


RETIRED_MENU_IDENTITIES = {
    119: ('ai:chat:list', 4, 'C'),
    1301: ('pipeline:governance:list', 1300, 'C'),
    1302: ('pipeline:governance:sync', 1301, 'F'),
    1303: ('pipeline:governance:operate', 1301, 'F'),
    2014: ('pipeline:report:publish', 2006, 'F'),
    2015: ('pipeline:prompt:list', 2009, 'F'),
    2016: ('pipeline:prompt:save', 2009, 'F'),
    2017: ('pipeline:prompt:test', 2009, 'F'),
    2018: ('pipeline:prompt:publish', 2009, 'F'),
    2021: ('pipeline:template:publish', 2008, 'F'),
    2026: ('pipeline:review:list', 2002, 'F'),
    2027: ('pipeline:review:operate', 2002, 'F'),
    2028: ('pipeline:review:reprocess', 2002, 'F'),
}
CHAT_MENU_ID = 119
MODEL_MENU_ID = 2009
COLLECTION_OPERATION_MENU_ID = 2025


def _menu_path(row: dict, by_id: dict, seen: frozenset = frozenset()) -> str | None:
    if row['id'] in seen:
        return None
    path = row.get('path') or ''
    if path.startswith('/'):
        return path.rstrip('/')
    parent = row.get('parent_id')
    if parent in (None, 0):
        return '/' + path.strip('/')
    if parent not in by_id:
        return None
    prefix = _menu_path(by_id[parent], by_id, seen | {row['id']})
    return prefix.rstrip('/') + '/' + path.strip('/') if prefix is not None else None


def project_menus(menus: list[dict], role_menus: list[dict]) -> dict:  # noqa: PLR0912, PLR0915
    """Only approved retired identities; reject repurposed IDs and unknown children."""
    by_id = {row['id']: row for row in menus}
    if len(by_id) != len(menus):
        raise SchemaPrerequisiteError('Duplicate menu IDs')
    retired = set()
    for identity, (permission, parent, kind) in RETIRED_MENU_IDENTITIES.items():
        row = by_id.get(identity)
        if row is None:
            continue
        if (row.get('permissions'), row.get('parent_id'), row.get('type')) != (permission, parent, kind):
            raise SchemaPrerequisiteError(f'Retired menu identity mismatch: {identity}')
        if kind == 'C':
            component, path = (('ai/chat/index', '/ai/chat') if identity == CHAT_MENU_ID
                               else ('pipeline/governance/index', '/pipeline/governance'))
            if row.get('component') != component or _menu_path(row, by_id) != path:
                raise SchemaPrerequisiteError(f'Retired menu route mismatch: {identity}')
        elif row.get('component') not in (None, '') or row.get('path') not in (None, '', '#'):
            raise SchemaPrerequisiteError(f'Retired button identity mismatch: {identity}')
        retired.add(identity)
    retired_permissions = {spec[0] for spec in RETIRED_MENU_IDENTITIES.values()}
    for row in menus:
        if row.get('permissions') in retired_permissions and row['id'] not in retired:
            raise SchemaPrerequisiteError(f'Retired permission under unapproved menu ID: {row["id"]}')
        component = row.get('component')
        path = _menu_path(row, by_id) if row.get('type') == 'C' else None
        if component == 'pipeline/filter/index' or path == '/pipeline/filter':
            if row.get('type') != 'C' or component not in (None, '', 'pipeline/filter/index'):
                raise SchemaPrerequisiteError('Retired filter menu identity mismatch')
            if row.get('permissions') not in (None, '', 'pipeline:filter:list', 'pipeline:prompt:list'):
                raise SchemaPrerequisiteError('Unapproved filter menu permission')
            retired.add(row['id'])
    if any(row['id'] not in retired and row.get('parent_id') in retired for row in menus):
        raise SchemaPrerequisiteError('Unapproved child of retired menu; explicit mapping required')
    output = []
    renamed = []
    for row in menus:
        if row['id'] in retired:
            continue
        changed = dict(row)
        if row['id'] == MODEL_MENU_ID:
            if (row.get('component') != 'pipeline/model/index' or row.get('type') != 'C'
                    or _menu_path(row, by_id) != '/pipeline/model'):
                raise SchemaPrerequisiteError('Model menu 2009 identity mismatch')
            changed['name'] = '模型与类别提示词'
        if row.get('component') == 'pipeline/intelligence/index' and '审核' in (row.get('name') or ''):
            if row.get('type') != 'C' or _menu_path(row, by_id) != '/pipeline/intelligence':
                raise SchemaPrerequisiteError('Intelligence menu identity mismatch')
            changed['name'] = '情报查询'
        if row['id'] == COLLECTION_OPERATION_MENU_ID:
            if (row.get('permissions'), row.get('parent_id'), row.get('type')) != ('pipeline:task:run', 2005, 'F'):
                raise SchemaPrerequisiteError('Collection operation menu 2025 identity mismatch')
            changed['name'] = '运行、停止与失败重试'
        if changed != row:
            renamed.append({'before': row, 'after': changed})
        output.append(changed)
    associations = [row for row in role_menus if row['menu_id'] not in retired]
    return {'menus': output, 'role_menus': associations,
            'archive': {'retired_menus': [row for row in menus if row['id'] in retired],
                        'retired_role_menus': [row for row in role_menus if row['menu_id'] in retired],
                        'renamed_menus': renamed},
            'source_fingerprints': {'menus': fingerprint(menus), 'role_menus': fingerprint(role_menus)},
            'target_fingerprints': {'menus': fingerprint(output), 'role_menus': fingerprint(associations)}}


def _json(value: Any) -> str:
    def encode(v: Any) -> Any:
        if isinstance(v, datetime) and v.tzinfo is not None:
            return v.astimezone(timezone.utc).isoformat()
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, (bytes, memoryview)):
            return {'base64': base64.b64encode(v).decode('ascii')}
        raise TypeError(f'Cannot fingerprint {type(v).__name__}')
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=encode,
                      separators=(',', ':'))


def fingerprint(rows: list[dict]) -> str:
    """Order independent, duplicate sensitive full-row SHA-256."""
    return hashlib.sha256(_json(sorted(_json(row) for row in rows)).encode()).hexdigest()


def _contract() -> dict:
    contract = load_contract('v1')
    if hashlib.sha256(_json(contract).encode()).hexdigest() != CONTRACT_SHA256:
        raise SchemaPrerequisiteError('Frozen compact-v1 contract changed; review migration before use')
    return contract


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _qualified(name: str) -> str:
    return '.'.join(_q(part) for part in name.split('.'))


def assert_rehearsal(bind: sa.Connection, *, allow_live: bool = False) -> None:
    """Fail closed before any query against an unapproved configured endpoint."""
    url = bind.engine.url
    if bind.dialect.name != 'postgresql':
        raise SchemaPrerequisiteError('PostgreSQL is required')
    if not allow_live and (url.host not in ('localhost', '127.0.0.1', '::1')
                           or url.port != REHEARSAL_PORT or url.database != 'pipesight_rehearsal'):
        raise SchemaPrerequisiteError('Only localhost:19432/pipesight_rehearsal is allowed without explicit allow_live')
    # Docker publishes 127.0.0.1:19432 -> container:5432. Its server address is
    # intentionally not loopback. The rehearsal runner verifies Docker's label
    # and published-port binding outside this connection-only module.
    if not url.database or bind.execute(sa.text('SELECT current_database()')).scalar_one() != url.database:
        raise SchemaPrerequisiteError('Unexpected rehearsal database')


def _timestamp(value: Any, timezone: str) -> datetime:
    if value is None:
        raise SchemaPrerequisiteError('Missing historical timestamp; refuse to invent one')
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(dt, datetime):
        raise SchemaPrerequisiteError('Invalid historical timestamp')
    return dt.replace(tzinfo=ZoneInfo(timezone)) if dt.tzinfo is None else dt


def paper_date(row: dict) -> str | None:
    """Use source precision only; the legacy published_at is approval time."""
    metadata = row.get('metadata_json') or {}
    value = metadata.get('original_date')
    if value is None and row.get('publication_year') is not None:
        value = str(row['publication_year'])
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}(-\d{2}){0,2}', value):
        raise SchemaPrerequisiteError('Invalid original paper date precision')
    try:
        date.fromisoformat(value + {4: '-01-01', 7: '-01', 10: ''}[len(value)])
    except (KeyError, ValueError) as exc:
        raise SchemaPrerequisiteError('Invalid original paper date') from exc
    if row.get('publication_year') and int(value[:4]) != int(row['publication_year']):
        raise SchemaPrerequisiteError('Conflicting paper date and publication year')
    return value


def _times(row: dict, timezone: str) -> dict:
    return {new: _timestamp(row.get(old), timezone)
            for old, new in [('create_time', 'created_at'), ('update_time', 'updated_at')]}


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaPrerequisiteError(f'Missing {label}; refuse invented content')
    return value


def _prompt(row: dict) -> str:
    # Preserve both roles, placeholders, and their order verbatim.
    return _json({'system_prompt': row.get('system_prompt'), 'user_prompt': row.get('user_prompt')})


@dataclass
class MigrationPlan:
    source: dict[str, list[dict]]
    target: dict[str, list[dict]]
    source_fingerprints: dict[str, str]
    timezone: str
    optional_tables: tuple[str, ...]
    menu_changes: dict | None = None
    access_contract: dict | None = None

    @property
    def summary(self) -> dict:
        return {'contract': _contract()['version'], 'timezone': self.timezone,
                'optional_tables': self.optional_tables,
                'physical_table_count': len(self.target) + len(self.optional_tables),
                'field_count': sum(len(t['columns']) for t in _contract()['tables']) + sum(len(COLUMN_COMMENTS[n]) for n in self.optional_tables),
                'menu_changes': self.menu_changes,
                'access_contract': self.access_contract,
                'source_counts': {k: len(v) for k, v in self.source.items()},
                'target_counts': {k: len(v) for k, v in self.target.items()},
                'source_fingerprints': self.source_fingerprints,
                'target_fingerprints': {k: fingerprint(v) for k, v in self.target.items()}}


def build_plan(source: dict[str, list[dict]], *, historical_timezone: str,  # noqa: PLR0912, PLR0915
               optional_tables: tuple[str, ...] = OPTIONAL_TABLE_NAMES) -> MigrationPlan:
    """Pure transform. Unsupported populated entities abort before SQL mutation."""
    ZoneInfo(historical_timezone)  # No implicit reinterpretation of old naive times.
    optional_tables = normalise_optional_tables(optional_tables)
    contract = _contract()
    if set(source) != SOURCE_TABLES:
        raise SchemaPrerequisiteError('Legacy table inventory differs from the approved 47-table baseline')
    allowed = MAPPED | {f'public.{n}' for n in BASE_TABLES.values()}
    for table, rows in source.items():
        if rows and table not in allowed:
            raise SchemaPrerequisiteError(f'Unmapped nonempty table {table}; explicit preservation mapping required')
    target = {t['name']: [] for t in contract['tables']}
    for table in contract['tables']:
        name = table['name']
        if name in BASE_TABLES:
            target[name] = [{c['name']: row.get(c['old_name'] or c['name'])
                             for c in table['columns']}
                            for row in source[f'public.{BASE_TABLES[name]}']]
    menu_changes = project_menus(target['menus'], target['role_menus'])
    target['menus'], target['role_menus'] = menu_changes['menus'], menu_changes['role_menus']

    prompts = source['public.prompt_versions']
    if any(r.get('scene') != 'data-filter' or r.get('status') != 'published' for r in prompts) or len(prompts) > 1:
        raise SchemaPrerequisiteError('Unmapped/ambiguous legacy prompt versions; explicit archive decision required')
    filter_prompt = _prompt(prompts[0]) if prompts else None
    prompt_used = False
    for row in source['news.domains']:
        if row.get('user_id') is not None:
            raise SchemaPrerequisiteError('Private domain cannot become global category')
        prompt = row.get('filter_prompts')
        if row.get('domain_name') == '油气管网' and filter_prompt:
            prompt = '\n\n'.join(p for p in (prompt, filter_prompt) if p)
            prompt_used = True
        # No classification criteria means a disabled category. Keep its actual
        # legacy remark as descriptive text; do not fabricate filtering rules.
        target['categories'].append(dict(
            id=str(row['domain_id']), name=_require_text(row.get('domain_name'), 'category name'),
            prompt=prompt or row.get('remark') or row['domain_name'], model_id=None,
            applies_to='all', is_enabled=False, sort_order=0, **_times(row, historical_timezone)))
    if filter_prompt and not prompt_used:
        raise SchemaPrerequisiteError('Filter prompt has no unambiguous 油气管网 category')

    sources: dict[tuple, str] = {}
    for row in source['public.news_articles']:
        if row.get('permission_scope') != 'public':
            raise SchemaPrerequisiteError('Private news cannot become public content')
        if row.get('source_id'):
            raise SchemaPrerequisiteError('Legacy source reference needs an explicit mapping')
        typ = {'news': 'website', 'website': 'website', 'wechat': 'wechat'}.get(row.get('article_type'))
        if typ is None:
            raise SchemaPrerequisiteError('Unmapped news source type')
        url = _require_text(row.get('canonical_url'), 'news URL')
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.netloc:
            raise SchemaPrerequisiteError('Invalid news source URL')
        # Keep exact entry URL: a domain root is not evidence of a crawl entry.
        key = (_require_text(row.get('source_name'), 'source name'), typ, url)
        if key not in sources:
            source_id = 'legacy-source-' + hashlib.sha256(_json(key).encode()).hexdigest()[:32]
            sources[key] = source_id
            target['data_sources'].append(dict(
                id=source_id, name=key[0], type=typ, url=url, adapter='manual',
                cron=None, timezone=historical_timezone, next_run_at=None, config={},
                model_id=None, is_enabled=False, **_times(row, historical_timezone)))
        metadata = row.get('metadata_json') or {}
        target['news_articles'].append(dict(
            id=row['article_id'], source_id=sources[key],
            title=_require_text(row.get('title'), 'news title'), url=url,
            author=row.get('author_text'),
            published_at=(_timestamp(row['published_time'], historical_timezone)
                          if row.get('published_time') is not None else None),
            content=row.get('body'), content_zh=metadata.get('content_zh'),
            category_id=None, is_pushed=False, **_times(row, historical_timezone)))
    for row in source['public.papers']:
        if row.get('permission_scope') != 'public':
            raise SchemaPrerequisiteError('Private paper cannot become public content')
        metadata = row.get('metadata_json') or {}
        if (metadata.get('full_text_imported') or
                any(metadata.get(k) for k in ('full_text', 'full_text_path', 'licensed_full_text', 'publisher_preview'))):
            raise SchemaPrerequisiteError('Stored paper full text requires explicit offline archival and reference review')
        if row.get('source_id'):
            raise SchemaPrerequisiteError('Legacy paper source reference needs explicit mapping')
        doi = row.get('doi_normalized') or row.get('doi')
        if doi:
            doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', doi, flags=re.I).strip().lower()
        if not doi and not row.get('canonical_url'):
            raise SchemaPrerequisiteError('Paper has neither DOI nor source URL')
        target['papers'].append(dict(
            id=row['paper_id'], source_id=None, title=_require_text(row.get('title'), 'paper title'),
            title_zh=metadata.get('title_zh'), url=row.get('canonical_url'), doi=doi,
            authors=row.get('authors'), journal=row.get('journal'), published_date=paper_date(row),
            abstract=row.get('abstract_text'), abstract_zh=metadata.get('abstract_zh'),
            category_id=None, is_pushed=False, **_times(row, historical_timezone)))
    for row in source['public.template_versions']:
        purpose = ('digest' if row.get('report_type') in ('daily', 'weekly', 'monthly')
                   else {'project-demand': 'research', 'research-demand': 'research',
                         'technology-route': 'research', 'article': 'article'}.get(row.get('report_type')))
        if purpose is None or not isinstance(row.get('sections'), list) or not row['sections']:
            raise SchemaPrerequisiteError('Template purpose/sections require explicit mapping')
        target['templates'].append(dict(
            id=row['template_id'], name=_require_text(row.get('name'), 'template name'),
            purpose=purpose, description=row.get('description'),
            # Legacy schema has no prompt column: serialize the actual template
            # specification instead of inventing a prompt or model config.
            prompt=_json({'name': row['name'], 'description': row.get('description'),
                          'report_type': row['report_type'], 'sections': row['sections']}),
            model_id=None, image_model_id=None, sections=row['sections'], image_config={},
            is_enabled=row.get('status') == 'published', **_times(row, historical_timezone)))
    item_columns = {'article': 'article_id', 'news': 'article_id', 'paper': 'paper_id',
                    'file': 'file_id', 'report': 'report_id'}
    for row in source['public.user_saved_items']:
        if row.get('item_type') not in item_columns or row.get('action') not in ('basket', 'favorite'):
            raise SchemaPrerequisiteError('Unmapped basket item type/action')
        result = dict.fromkeys(('article_id', 'paper_id', 'file_id', 'report_id'))
        result.update(id=row['saved_item_id'], user_id=row['user_id'], action=row['action'],
                      created_at=_timestamp(row['create_time'], historical_timezone))
        result[item_columns[row['item_type']]] = row['item_id']
        target['basket_items'].append(result)
    _validate_rows(target, contract)
    return MigrationPlan(source, target, {k: fingerprint(v) for k, v in source.items()},
                         historical_timezone, optional_tables, menu_changes)


def _validate_rows(target: dict, contract: dict) -> None:  # noqa: PLR0912
    for table in contract['tables']:
        name = table['name']
        cols = table['columns']
        pk = [c['name'] for c in cols if c['primary_key']]
        seen = set()
        for row in target[name]:
            if set(row) != {c['name'] for c in cols}:
                raise SchemaPrerequisiteError(f'Incorrect target fields: {name}')
            identity = tuple(row[k] for k in pk)
            if identity in seen:
                raise SchemaPrerequisiteError(f'Duplicate target primary key: {name}')
            seen.add(identity)
            for c in cols:
                value = row[c['name']]
                if value is None and not c['nullable']:
                    raise SchemaPrerequisiteError(f'Missing target value: {name}.{c["name"]}')
                length = re.search(r'(?:varchar|character varying)\((\d+)\)', c['type'])
                if length and isinstance(value, str) and len(value) > int(length[1]):
                    raise SchemaPrerequisiteError(f'Target text too long: {name}.{c["name"]}')
    for fk in contract['foreign_keys']:
        referenced = {tuple(r[c] for c in fk['target_columns']) for r in target[fk['target']]}
        for row in target[fk['table']]:
            key = tuple(row[c] for c in fk['columns'])
            if all(v is not None for v in key) and key not in referenced:
                raise SchemaPrerequisiteError(f'Orphan target reference: {fk["table"]}.{fk["columns"]}')
    unique = [('news_articles', 'url'), ('papers', 'doi'), ('papers', 'url'), ('categories', 'name'),
              ('users', 'username'), ('roles', 'code'), ('settings', 'key'), ('dict_types', 'code')]
    for table, col in unique:
        values = [r[col] for r in target[table] if r[col] is not None
                  and not (table == 'papers' and col == 'url' and r['doi'] is not None)]
        if len(values) != len(set(values)):
            raise SchemaPrerequisiteError(f'Duplicate target unique value: {table}.{col}')
    for row in target['basket_items']:
        if sum(row[c] is not None for c in ('article_id', 'paper_id', 'file_id', 'report_id')) != 1:
            raise SchemaPrerequisiteError('Basket must have exactly one source')


def _inventory(bind: sa.Connection) -> set[str]:
    return set(bind.execute(sa.text("""
        SELECT n.nspname || '.' || c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','news') AND c.relkind IN ('r','p')
    """)).scalars())


def preflight(bind: sa.Connection, *, historical_timezone: str,
              optional_tables: tuple[str, ...] = OPTIONAL_TABLE_NAMES, allow_live: bool = False) -> MigrationPlan:
    assert_rehearsal(bind, allow_live=allow_live)
    if _inventory(bind) != SOURCE_TABLES:
        raise SchemaPrerequisiteError('Expected exactly the approved 47 legacy physical tables')
    source = {name: [dict(row) for row in bind.execute(sa.text(
        f'SELECT * FROM {_qualified(name)}')).mappings()] for name in sorted(SOURCE_TABLES)}
    # Exact base-field set: column drops are never silently folded into rename.
    for table in _contract()['tables']:
        if table['name'] in BASE_TABLES:
            old = BASE_TABLES[table['name']]
            columns = {c['name'] for c in sa.inspect(bind).get_columns(old, schema='public')}
            if columns != {c['old_name'] or c['name'] for c in table['columns']}:
                raise SchemaPrerequisiteError(f'Unexpected foundation fields: {old}')
    plan = build_plan(source, historical_timezone=historical_timezone, optional_tables=optional_tables)
    plan.access_contract = inspect_access_contract(bind)
    return plan


def inspect_access_contract(bind: sa.Connection) -> dict:
    """Snapshot ACL/owners without changing grants; reject loss on rebuilt public objects."""
    role = bind.execute(sa.text('SELECT current_user')).scalar_one()
    relations = [dict(row) for row in bind.execute(sa.text("""
        SELECT c.oid::bigint AS oid,n.nspname AS schema,c.relname AS name,
               c.relkind::text AS kind,pg_get_userbyid(c.relowner) AS owner,c.relacl::text AS acl,
               (SELECT nt.nspname||'.'||t.relname FROM pg_depend d JOIN pg_class t ON t.oid=d.refobjid
                JOIN pg_namespace nt ON nt.oid=t.relnamespace WHERE d.objid=c.oid
                AND d.classid='pg_class'::regclass AND d.refclassid='pg_class'::regclass
                AND d.deptype IN ('a','i') LIMIT 1) AS owned_table
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','news') AND c.relkind IN ('r','p','S') ORDER BY n.nspname,c.relname
    """)).mappings()]
    columns = [dict(row) for row in bind.execute(sa.text("""
        SELECT a.attrelid::bigint AS oid,a.attnum,a.attacl::text AS acl,n.nspname AS schema,c.relname AS name
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','news') AND a.attnum>0 AND NOT a.attisdropped AND a.attacl IS NOT NULL
        ORDER BY a.attrelid,a.attnum
    """)).mappings()]
    defaults = [dict(row) for row in bind.execute(sa.text("""
        SELECT pg_get_userbyid(d.defaclrole) AS owner,coalesce(n.nspname,'') AS schema,
               d.defaclobjtype::text AS type,d.defaclacl::text AS acl
        FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
        ORDER BY d.defaclrole,d.defaclnamespace,d.defaclobjtype
    """)).mappings()]
    grants = [dict(row) for row in bind.execute(sa.text("""
        SELECT n.nspname AS schema,c.relname AS name,x.grantee::bigint AS grantee,x.privilege_type
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL aclexplode(c.relacl) x
        WHERE n.nspname='public' AND x.grantee<>c.relowner
    """)).mappings()]
    retired = {'public.' + n for n in PUBLIC_BUSINESS}
    for row in relations:
        if (row['schema']+'.'+row['name'] in retired or row['owned_table'] in retired) and row['owner'] != role:
            raise SchemaPrerequisiteError('Migration role differs from rebuilt public object owner; explicit ACL policy required')
    if any(r['schema']+'.'+r['name'] in retired for r in grants + columns):
        raise SchemaPrerequisiteError('Third-party or column grants on rebuilt public tables require explicit preservation')
    retiring_sequences = {r['name'] for r in relations if r['owned_table'] in retired}
    if any(r['name'] in retiring_sequences for r in grants):
        raise SchemaPrerequisiteError('Third-party sequence grants require explicit preservation')
    if any(r['schema'] in ('', 'public') for r in defaults):
        raise SchemaPrerequisiteError('Global/public default privileges require explicit new-object ACL review')
    return {'role': role, 'relations': relations, 'column_acls': columns, 'default_acls': defaults}


def verify_access_contract(bind: sa.Connection, before: dict, optional_tables: tuple[str, ...]) -> dict:
    after = inspect_access_contract(bind)
    old_base = {'public.' + name for name in BASE_TABLES.values()}
    protected = [r for r in before['relations'] if r['schema']+'.'+r['name'] in old_base or r['owned_table'] in old_base]
    actual = {r['oid']: r for r in after['relations']}
    for row in protected:
        current = actual.get(row['oid'])
        if current is None or any(current[k] != row[k] for k in ('owner', 'kind', 'acl')):
            raise SchemaPrerequisiteError('Foundation owner/ACL/sequence changed during rename')
    old_column_acls = {(r['oid'], r['attnum']): r['acl'] for r in before['column_acls'] if r['oid'] in {x['oid'] for x in protected}}
    new_column_acls = {(r['oid'], r['attnum']): r['acl'] for r in after['column_acls'] if r['oid'] in {x['oid'] for x in protected}}
    if old_column_acls != new_column_acls or before['default_acls'] != after['default_acls']:
        raise SchemaPrerequisiteError('Foundation column grants or default ACLs changed')
    names = {t['name'] for t in _contract()['tables'] if t['name'] not in BASE_TABLES} | set(optional_tables)
    if any(r['owner'] != before['role'] for r in after['relations'] if r['schema'] == 'public' and r['name'] in names):
        raise SchemaPrerequisiteError('Rebuilt business owner differs from migration connection role')
    return {'foundation_owner_acl_preserved': True, 'business_owner': before['role'],
            'public_third_party_grants_detected': False, 'news_acl_restoration_claimed': False}


def verify_source_snapshot(bind: sa.Connection, snapshot: dict, *, allow_live: bool = False) -> None:
    """Match the existing pg_dump manifest's count/PG-row-JSON MD5 recipe.

    This is additional to the SHA-256 projections in the retirement archive.
    It proves the approved backup describes the actual source being migrated.
    No URL/host in an input manifest is ever used to open a connection.
    """
    assert_rehearsal(bind, allow_live=allow_live)
    expected = snapshot.get('fingerprints', {})
    if set(expected) != SOURCE_TABLES or _inventory(bind) != SOURCE_TABLES:
        raise SchemaPrerequisiteError('Source backup manifest must cover exactly all 47 tables')
    for name in sorted(SOURCE_TABLES):
        row = bind.execute(sa.text(
            "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
            f'(SELECT md5(row_to_json(t)::text) h FROM {_qualified(name)} t) s')).one()
        if list(row) != list(expected[name]):
            raise SchemaPrerequisiteError(f'Approved backup source fingerprint mismatch: {name}')


def archive_plan(plan: MigrationPlan, path: str | Path) -> str:
    """Persist retired business fields/events before DDL; exclusive 0600 file.

    Base rows (including password hashes) are preserved in-place, and only their
    fingerprints appear here. No model credentials are accepted by build_plan.
    This is a supplementary retirement archive, not a replacement for pg_dump.
    """
    path = Path(path)
    payload = {'summary': plan.summary,
               'foundation_menu_archive': plan.menu_changes,
               'retired_business_rows': {
        k: v for k, v in plan.source.items() if k not in
        {f'public.{n}' for n in BASE_TABLES.values()}}}
    encoded = _json(payload).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    digest = hashlib.sha256(encoded).hexdigest()
    _verify_archive(plan, path, digest)
    return digest


def _verify_archive(plan: MigrationPlan, path: str | Path, digest: str) -> None:
    path = Path(path)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise SchemaPrerequisiteError('Retirement archive must be a private regular file')
    encoded = path.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != digest:
        raise SchemaPrerequisiteError('Retirement archive SHA-256 mismatch')
    payload = json.loads(encoded)
    if payload.get('summary') != json.loads(_json(plan.summary)):
        raise SchemaPrerequisiteError('Retirement archive is stale or has different options')
    expected = {k: v for k, v in plan.source.items() if k not in
                {f'public.{n}' for n in BASE_TABLES.values()}}
    if payload.get('retired_business_rows') != json.loads(_json(expected)):
        raise SchemaPrerequisiteError('Retirement archive content differs from source')
    if payload.get('foundation_menu_archive') != json.loads(_json(plan.menu_changes)):
        raise SchemaPrerequisiteError('Foundation menu archive mismatch')


def apply_menu_changes(bind: sa.Connection, changes: dict) -> None:
    """Caller holds locks and has verified the archive; delete known IDs only."""
    current = {name: [dict(r) for r in bind.execute(sa.text(f'SELECT * FROM public.{name}')).mappings()]
               for name in ('menus', 'role_menus')}
    actual = {name: fingerprint(rows) for name, rows in current.items()}
    if actual != changes['source_fingerprints']:
        raise SchemaPrerequisiteError('Foundation menus changed after preflight')
    keys = [fk for fk in sa.inspect(bind).get_foreign_keys('role_menus', schema='public')
            if fk['constrained_columns'] == ['menu_id'] and fk['referred_table'] == 'menus']
    if len(keys) != 1 or keys[0].get('options', {}).get('ondelete') != 'CASCADE':
        raise SchemaPrerequisiteError('Menu role relation requires its exact ON DELETE CASCADE foreign key')
    # Parent trees have no database FK. project_menus rejects any unapproved
    # surviving child; only the individually verified menu IDs are deleted.
    for row in changes['archive']['retired_menus']:
        bind.execute(sa.text('DELETE FROM public.menus WHERE id=:id'), {'id': row['id']})
    for pair in changes['archive']['renamed_menus']:
        bind.execute(sa.text('UPDATE public.menus SET name=:name WHERE id=:id'),
                     {'id': pair['after']['id'], 'name': pair['after']['name']})
    for name in ('menus', 'role_menus'):
        rows = [dict(r) for r in bind.execute(sa.text(f'SELECT * FROM public.{name}')).mappings()]
        if fingerprint(rows) != changes['target_fingerprints'][name]:
            raise SchemaPrerequisiteError(f'Foundation menu projection mismatch: {name}')


def patch_final_rehearsal(bind: sa.Connection, archive_path: str | Path) -> dict:
    """Authorized local-only 30->29 patch; never resets the running API's DB."""
    if not bind.in_transaction():
        raise SchemaPrerequisiteError('A caller-owned transaction is required')
    assert_rehearsal(bind)
    with bind.begin_nested():
        bind.exec_driver_sql("SET LOCAL lock_timeout='5s'")
        names = _inventory(bind)
        approved = {'public.' + n for n in TABLE_COMMENTS}
        if names not in (approved, approved | {'public.chat_settings'}):
            raise SchemaPrerequisiteError('Final patch requires the exact canonical rehearsal inventory')
        bind.exec_driver_sql('LOCK TABLE ' + ','.join(_qualified(n) for n in sorted(names)) + ' IN ACCESS EXCLUSIVE MODE')
        rows = {n: [dict(r) for r in bind.execute(sa.text(f'SELECT * FROM {_qualified(n)}')).mappings()]
                for n in sorted(names)}
        if rows.get('public.chat_settings'):
            raise SchemaPrerequisiteError('Personal chat preferences are nonempty; explicit preservation mapping required')
        changes = project_menus(rows['public.menus'], rows['public.role_menus'])
        payload = {'approved_optional_tables': list(OPTIONAL_TABLE_NAMES),
                   'foundation_menu_archive': changes, 'retired_chat_settings': rows.get('public.chat_settings', []),
                   'source_fingerprints': {n: fingerprint(v) for n, v in rows.items()}}
        encoded = _json(payload).encode()
        path = Path(archive_path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        digest = hashlib.sha256(encoded).hexdigest()
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SchemaPrerequisiteError('Final rehearsal archive digest mismatch')
        apply_menu_changes(bind, changes)
        if 'public.chat_settings' in names:
            bind.exec_driver_sql('DROP TABLE public.chat_settings RESTRICT')
        apply_schema_comments(bind)
        for name, before in rows.items():
            if name in ('public.menus', 'public.role_menus', 'public.chat_settings'):
                continue
            after = [dict(r) for r in bind.execute(sa.text(f'SELECT * FROM {_qualified(name)}')).mappings()]
            if fingerprint(before) != fingerprint(after):
                raise SchemaPrerequisiteError(f'Unrelated data changed during final patch: {name}')
        return {'tables': len(_inventory(bind)), 'fields': sum(map(len, COLUMN_COMMENTS.values())),
                'retired_menus': [r['id'] for r in changes['archive']['retired_menus']],
                'renamed_menus': [p['after']['id'] for p in changes['archive']['renamed_menus']],
                'archive_path': str(path), 'archive_sha256': digest}


def _type(value: str) -> sa.types.TypeEngine:
    if value == 'ID':
        return sa.String(64)
    if value == '时间':
        return sa.DateTime(timezone=True)
    if value == 'jsonb':
        return JSONB()
    names = {'bigint': sa.BigInteger, 'integer': sa.Integer, 'smallint': sa.SmallInteger,
             'boolean': sa.Boolean, 'text': sa.Text, 'time': sa.Time}
    if value in names:
        return names[value]()
    if re.fullmatch(r'varchar\(\d+\)', value):
        return sa.String(int(re.search(r'\d+', value)[0]))
    raise SchemaPrerequisiteError(f'Unsupported business type: {value}')


def _delete_rule(fk: dict) -> str:
    table, col = fk['table'], fk['columns'][0]
    if table in ('user_roles', 'role_menus', 'dict_items', 'basket_items'):
        return 'CASCADE'
    if (table, col) in {('generation_tasks', 'report_id'), ('report_assets', 'report_id')}:
        return 'CASCADE'
    if (table, col) in {('papers', 'source_id'), ('job_logs', 'job_id')}:
        return 'SET NULL'
    return 'RESTRICT'


DEFAULTS = {
    'is_enabled': 'true', 'is_pushed': 'false', 'sort_order': '0', 'version': '1',
    'attempts': '0', 'progress': '0', 'fetched_count': '0', 'saved_count': '0', 'failed_count': '0',
    'created_at': 'CURRENT_TIMESTAMP', 'updated_at': 'CURRENT_TIMESTAMP',
    'timezone': "'Asia/Shanghai'", 'applies_to': "'all'",
    'config': "'{}'::jsonb", 'parameters': "'{}'::jsonb", 'image_config': "'{}'::jsonb",
    'config_snapshot': "'{}'::jsonb", 'checkpoint': "'{}'::jsonb",
    'generation_config': "'{}'::jsonb", 'sections': "'[]'::jsonb", 'materials': "'[]'::jsonb",
}


def target_metadata(*, optional_tables: tuple[str, ...] = ()) -> sa.MetaData:
    """Build only business tables; existing foundation objects stay in-place."""
    optional_tables = normalise_optional_tables(optional_tables)
    metadata = sa.MetaData(schema='public')
    for spec in _contract()['tables']:
        if spec['name'] in BASE_TABLES:
            continue
        columns = []
        for c in spec['columns']:
            default = DEFAULTS.get(c['name'])
            if c['name'] == 'status':
                default = "'queued'"
            if spec['name'] == 'reports' and c['name'] == 'content':
                default = "''"
            if spec['name'] in ('basket_items', 'ai_models') and c['name'] == 'id':
                columns.append(sa.Column('id', sa.BigInteger, sa.Identity(), primary_key=True))
            else:
                columns.append(sa.Column(c['name'], _type(c['type']),
                                         nullable=c['nullable'], primary_key=c['primary_key'],
                                         autoincrement=False,
                                         server_default=sa.text(default) if default else None))
        sa.Table(spec['name'], metadata, *columns)
    if optional_tables:
        _optional_metadata(metadata)
        for name in set(OPTIONAL_TABLE_NAMES) - set(optional_tables):
            metadata.remove(metadata.tables['public.' + name])
    for table in metadata.tables.values():
        if set(table.c.keys()) != set(COLUMN_COMMENTS[table.name]):
            raise SchemaPrerequisiteError(f'Business comment fields mismatch: {table.name}')
        table.comment = TABLE_COMMENTS[table.name]
        for column in table.c:
            column.comment = COLUMN_COMMENTS[table.name][column.name]
    return metadata


def _optional_metadata(metadata: sa.MetaData) -> None:
    """Frozen fields agreed with the model owners; legacy rows must be empty."""
    def col(name: str, type_: Any, nullable: bool = True, **kwargs) -> sa.Column:
        return sa.Column(name, type_, nullable=nullable, **kwargs)
    sa.Table('model_calls', metadata,
             col('id', sa.String(64), False, primary_key=True),
             col('task_id', sa.String(64)), col('model_id', sa.BigInteger, False),
             col('capability', sa.String(32), False), col('status', sa.String(16), False),
             col('duration_ms', sa.Integer, False), col('input_tokens', sa.Integer),
             col('output_tokens', sa.Integer), col('error', sa.Text),
             col('created_at', sa.DateTime(timezone=True), False, server_default=sa.text('CURRENT_TIMESTAMP')))
    sa.Table('report_versions', metadata,
             sa.Column('id', sa.BigInteger, sa.Identity(), primary_key=True),
             col('report_id', sa.String(64), False), col('version', sa.Integer, False),
             col('title', sa.String(1000), False), col('content', sa.Text, False),
             col('sections', JSONB, False), col('citations', JSONB, False),
             col('quality_issues', JSONB, False), col('model_snapshot', JSONB, False),
             col('source', sa.String(32), False), col('operator_id', sa.BigInteger),
             col('operator_name', sa.String(64), False),
             col('created_at', sa.DateTime(timezone=True), False, server_default=sa.text('CURRENT_TIMESTAMP')))


CHECKS = {
    'news_articles': ["length(btrim(title))>0 AND length(btrim(url))>0"],
    'papers': ["length(btrim(title))>0 AND (nullif(btrim(doi),'') IS NOT NULL OR nullif(btrim(url),'') IS NOT NULL)",
               "published_date IS NULL OR CASE WHEN published_date ~ '^[0-9]{4}(-[0-9]{2}){0,2}$' THEN make_date(substring(published_date,1,4)::int,coalesce(nullif(substring(published_date,6,2),'')::int,1),coalesce(nullif(substring(published_date,9,2),'')::int,1)) IS NOT NULL ELSE false END"],
    'categories': ["applies_to IN ('news','paper','all')", "length(btrim(name))>0 AND length(btrim(prompt))>0",
                   "NOT is_enabled OR model_id IS NOT NULL"],
    'data_sources': ["type IN ('website','wechat','paper')", "length(btrim(name))>0 AND length(btrim(adapter))>0",
                     "jsonb_typeof(config)='object'",
                     "CASE WHEN is_enabled AND cron IS NOT NULL THEN next_run_at IS NOT NULL ELSE next_run_at IS NULL END"],
    'knowledge_files': ["size>=0 AND version>=1", "status IN ('queued','parsing','ready','failed')"],
    'templates': ["purpose IN ('article','research','digest')", "length(btrim(prompt))>0 AND length(btrim(name))>0",
                  "jsonb_typeof(sections)='array' AND jsonb_typeof(image_config)='object'"],
    'ai_models': ["jsonb_typeof(capabilities)='array' AND jsonb_typeof(parameters)='object'"],
    'reports': ["version>=1", "type IN ('article','research','daily','weekly','monthly')", "length(btrim(title))>0"],
    'generation_tasks': ["status IN ('queued','running','completed','failed','cancelled')",
                         "progress BETWEEN 0 AND 100 AND attempts>=0",
                         "jsonb_typeof(config_snapshot)='object'",
                         "CASE WHEN jsonb_typeof(materials)='array' THEN jsonb_array_length(materials)<=50 ELSE false END",
                         "finished_at IS NULL OR started_at IS NULL OR finished_at>=started_at"],
    'report_assets': ["type IN ('image','export')", "status IN ('queued','running','completed','failed')",
                      "status<>'completed' OR nullif(btrim(storage_key),'') IS NOT NULL",
                      "jsonb_typeof(config_snapshot)='object' AND length(btrim(mime_type))>0",
                      "CASE WHEN type='image' THEN model_id IS NOT NULL AND nullif(btrim(prompt),'') IS NOT NULL ELSE model_id IS NULL AND prompt IS NULL AND position IS NULL END"],
    'digest_schedules': ["(frequency='daily' AND weekday IS NULL AND month_day IS NULL) OR (frequency='weekly' AND weekday IS NOT NULL AND weekday BETWEEN 0 AND 6 AND month_day IS NULL) OR (frequency='monthly' AND month_day IS NOT NULL AND month_day BETWEEN 1 AND 31 AND weekday IS NULL)",
                         "NOT is_enabled OR next_run_at IS NOT NULL",
                         "jsonb_typeof(selection_config)='object' AND jsonb_typeof(generation_config)='object'"],
    'basket_items': ["action IN ('basket','favorite')", "num_nonnulls(article_id,paper_id,file_id,report_id)=1"],
    'collection_runs': ["trigger_type IN ('manual','schedule','retry')",
                        "status IN ('queued','running','stopping','success','failed','cancelled')",
                        "parent_id IS NULL OR parent_id<>id",
                        "CASE WHEN trigger_type='retry' THEN parent_id IS NOT NULL ELSE parent_id IS NULL END",
                        "fetched_count>=0 AND saved_count>=0 AND failed_count>=0 AND saved_count+failed_count<=fetched_count",
                        "jsonb_typeof(config_snapshot)='object' AND jsonb_typeof(checkpoint)='object'",
                        "created_at<=available_at AND (started_at IS NULL OR started_at>=created_at) AND (finished_at IS NULL OR finished_at>=coalesce(started_at,created_at))",
                        "CASE WHEN status='queued' THEN started_at IS NULL AND finished_at IS NULL AND execution_token IS NULL AND lease_expires_at IS NULL AND stop_requested_at IS NULL WHEN status='running' THEN started_at IS NOT NULL AND finished_at IS NULL AND execution_token IS NOT NULL AND lease_expires_at IS NOT NULL AND stop_requested_at IS NULL WHEN status='stopping' THEN started_at IS NOT NULL AND finished_at IS NULL AND stop_requested_at IS NOT NULL AND ((execution_token IS NULL AND lease_expires_at IS NULL) OR (execution_token IS NOT NULL AND lease_expires_at IS NOT NULL)) ELSE finished_at IS NOT NULL AND execution_token IS NULL AND lease_expires_at IS NULL END",
                        "status NOT IN ('stopping','cancelled') OR stop_requested_at IS NOT NULL",
                        "status<>'failed' OR nullif(btrim(error),'') IS NOT NULL",
                        "status<>'success' OR (failed_count=0 AND error IS NULL)"],
}


def _constraints(bind: sa.Connection, *, optional_tables: tuple[str, ...]) -> None:  # noqa: PLR0912
    def run(sql: str) -> None:
        bind.exec_driver_sql(sql)
    for table, expressions in CHECKS.items():
        for i, expression in enumerate(expressions):
            run(f'ALTER TABLE public.{_q(table)} ADD CONSTRAINT {_q(f"ck_{table}_{i}")} CHECK ({expression})')
    uniques = {'users': [('username',)], 'roles': [('code',)], 'settings': [('key',)],
               'dict_types': [('code',)], 'categories': [('name',)],
               'generation_tasks': [('request_id',), ('id', 'report_id')],
               'collection_runs': [('request_id',), ('id', 'source_id')]}
    inspector = sa.inspect(bind)
    for table, groups in uniques.items():
        existing = {tuple(x['column_names']) for x in inspector.get_unique_constraints(table, schema='public')}
        existing |= {tuple(x['column_names']) for x in inspector.get_indexes(table, schema='public') if x['unique'] and not x.get('dialect_options', {}).get('postgresql_where')}
        for cols in groups:
            if cols not in existing:
                run(f'ALTER TABLE public.{_q(table)} ADD CONSTRAINT {_q("uk_"+table+"_"+"_".join(cols))} UNIQUE ({",".join(map(_q, cols))})')
    inspector = sa.inspect(bind)
    for fk in _contract()['foreign_keys']:
        table = fk['table']
        cols = fk['columns']
        # Existing foundation constraints update automatically on rename.
        existing = inspector.get_foreign_keys(table, schema='public')
        matching = [f for f in existing if f['constrained_columns'] == cols and f['referred_table'] == fk['target'] and f['referred_columns'] == fk['target_columns']]
        if matching:
            continue
        name = ('fk_' + table + '_' + '_'.join(cols))[:63]
        onupdate = ' ON UPDATE CASCADE' if table == 'dict_items' else ''
        run(f'ALTER TABLE public.{_q(table)} ADD CONSTRAINT {_q(name)} FOREIGN KEY ({",".join(map(_q, cols))}) REFERENCES public.{_q(fk["target"])} ({",".join(map(_q, fk["target_columns"]))}) ON DELETE {_delete_rule(fk)}{onupdate}')
    indexes = [
        ('news_articles_url', 'news_articles', '(md5(url))', None, True),
        ('papers_doi', 'papers', '(doi)', 'doi IS NOT NULL', True),
        ('papers_url', 'papers', '(md5(url))', 'doi IS NULL AND url IS NOT NULL', True),
        ('news_articles_published_at', 'news_articles', '(published_at DESC,id)', None, False),
        ('news_articles_source_id', 'news_articles', '(source_id,published_at DESC,id)', None, False),
        ('news_articles_category_id', 'news_articles', '(category_id,published_at DESC,id)', None, False),
        ('papers_category_id', 'papers', "(category_id, (rpad(published_date,10,'-01')) DESC,id)", None, False),
        ('knowledge_files_user_id', 'knowledge_files', '(user_id,updated_at DESC)', None, False),
        ('reports_user_id', 'reports', '(user_id,updated_at DESC,id)', None, False),
        ('generation_tasks_status', 'generation_tasks', '(status,created_at)', None, False),
        ('generation_tasks_report_id', 'generation_tasks', '(report_id)', None, False),
        ('generation_tasks_lease', 'generation_tasks', '(lease_expires_at)', 'lease_expires_at IS NOT NULL', False),
        ('report_assets_report_id', 'report_assets', '(report_id,created_at)', None, False),
        ('digest_schedules_next_run_at', 'digest_schedules', '(next_run_at)', 'is_enabled', False),
        ('data_sources_next_run_at', 'data_sources', '(next_run_at)', 'is_enabled AND cron IS NOT NULL', False),
        ('collection_runs_source_id', 'collection_runs', '(source_id,created_at DESC,id)', None, False),
        ('collection_runs_status', 'collection_runs', '(status,available_at)', None, False),
        ('collection_runs_lease', 'collection_runs', '(lease_expires_at)', "status IN ('running','stopping')", False),
        ('collection_runs_active', 'collection_runs', '(source_id)', "status IN ('queued','running','stopping')", True),
        ('collection_runs_parent_id', 'collection_runs', '(parent_id)', 'parent_id IS NOT NULL', True),
    ]
    indexes.extend(('basket_items_'+col, 'basket_items', f'(user_id,action,{col})', f'{col} IS NOT NULL', True)
                   for col in ('article_id', 'paper_id', 'file_id', 'report_id'))
    for name, table, expr, where, unique in indexes:
        run(f'CREATE {"UNIQUE " if unique else ""}INDEX {_q(("uk_" if unique else "idx_")+name)} ON public.{_q(table)} {expr}' + (f' WHERE {where}' if where else ''))
    if optional_tables:
        for table, columns, target, target_columns, rule in OPTIONAL_FKS:
            if table not in optional_tables:
                continue
            run(f'ALTER TABLE public.{_q(table)} ADD CONSTRAINT {_q("fk_"+table+"_"+columns[0])} FOREIGN KEY ({",".join(map(_q, columns))}) REFERENCES public.{_q(target)} ({",".join(map(_q,target_columns))}) ON DELETE {rule}')
    if 'report_versions' in optional_tables:
        run('ALTER TABLE public.report_versions ADD CONSTRAINT uk_report_versions_report_id_version UNIQUE(report_id,version), ADD CONSTRAINT ck_report_versions_version CHECK(version>=1)')
    if 'model_calls' in optional_tables:
        run("ALTER TABLE public.model_calls ADD CONSTRAINT ck_model_calls_capability CHECK(capability IN ('text_generate','image_generate')), ADD CONSTRAINT ck_model_calls_status CHECK(status IN ('success','failed')), ADD CONSTRAINT ck_model_calls_duration_ms CHECK(duration_ms>=0), ADD CONSTRAINT ck_model_calls_input_tokens CHECK(input_tokens IS NULL OR input_tokens>=0), ADD CONSTRAINT ck_model_calls_output_tokens CHECK(output_tokens IS NULL OR output_tokens>=0)")
        run('CREATE INDEX idx_model_calls_model_id_created_at ON public.model_calls(model_id,created_at)')
        run('CREATE INDEX idx_model_calls_task_id_created_at ON public.model_calls(task_id,created_at)')


OPTIONAL_FKS = [
    ('model_calls', ['task_id'], 'generation_tasks', ['id'], 'SET NULL'),
    ('model_calls', ['model_id'], 'ai_models', ['id'], 'RESTRICT'),
    ('report_versions', ['report_id'], 'reports', ['id'], 'CASCADE'),
    ('report_versions', ['operator_id'], 'users', ['id'], 'SET NULL'),
]


def _comment_sql(kind: str, table: str, column: str | None, comment: str) -> str:
    identifier = 'public.' + _q(table) + ('.' + _q(column) if column is not None else '')
    literal = "'" + comment.replace("'", "''") + "'"
    return f'COMMENT ON {kind} {identifier} IS {literal};'


def render_comment_sql() -> str:
    """Deterministic canonical SQL; optional/framework/catalog objects guarded."""
    lines = [
        '-- 精简结构中文注释；数据源为 app/schema_comments.py。',
        '-- 27张基线表317字段，2张保留功能表23字段；共29张物理表340字段。',
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


def _type_signature(value: str) -> str:
    if value.upper() in ('FLOAT', 'FLOAT(53)', 'DOUBLE PRECISION'):
        return 'doubleprecision'
    return (value.lower().replace('character varying', 'varchar').replace('character(', 'char(')
            .replace('timestamp with time zone', 'timestamptz')
            .replace('timestamp without time zone', 'timestamp')
            .replace('time without time zone', 'time').replace(' ', ''))


def verify_target(bind: sa.Connection, plan: MigrationPlan) -> dict:  # noqa: PLR0912, PLR0915
    """Exact physical table/field/PK/FK lists plus full projected row digests."""
    contract = _contract()
    expected = {'public.'+t['name'] for t in contract['tables']}
    if plan.optional_tables:
        expected |= {'public.'+t for t in plan.optional_tables}
    if _inventory(bind) != expected:
        raise SchemaPrerequisiteError('Post-migration physical table inventory mismatch')
    inspector = sa.inspect(bind)
    types = {(r[0], r[1]): r[2] for r in bind.execute(sa.text("""
        SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod)
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped AND c.relkind='r'
    """))}
    digests = {}
    for table in contract['tables']:
        name = table['name']
        fields = inspector.get_columns(name, schema='public')
        if [c['name'] for c in fields] != [c['name'] for c in table['columns']]:
            raise SchemaPrerequisiteError(f'Post-migration field list mismatch: {name}')
        if {c['name']: c['nullable'] for c in fields} != {c['name']: c['nullable'] for c in table['columns']}:
            raise SchemaPrerequisiteError(f'Post-migration nullable mismatch: {name}')
        for col in table['columns']:
            expected_type = {'ID': 'varchar(64)', '时间': 'timestamptz'}.get(col['type'], col['type'])
            if _type_signature(types[name, col['name']]) != _type_signature(expected_type):
                raise SchemaPrerequisiteError(f'Post-migration type mismatch: {name}.{col["name"]}')
        pk = inspector.get_pk_constraint(name, schema='public')['constrained_columns']
        if pk != [c['name'] for c in table['columns'] if c['primary_key']]:
            raise SchemaPrerequisiteError(f'Post-migration PK mismatch: {name}')
        rows = [dict(r) for r in bind.execute(sa.text(f'SELECT * FROM public.{_q(name)}')).mappings()]
        # Alembic updates its version after this function returns.
        if fingerprint(rows) != fingerprint(plan.target[name]):
            raise SchemaPrerequisiteError(f'Post-migration content fingerprint mismatch: {name}')
        digests[name] = fingerprint(rows)
    actual_fks = set()
    for t in contract['tables']:
        for fk in inspector.get_foreign_keys(t['name'], schema='public'):
            actual_fks.add((t['name'], tuple(fk['constrained_columns']), fk['referred_table'], tuple(fk['referred_columns'])))
    expected_fks = {(f['table'], tuple(f['columns']), f['target'], tuple(f['target_columns'])) for f in contract['foreign_keys']}
    if actual_fks != expected_fks:
        raise SchemaPrerequisiteError('Post-migration FK list mismatch')
    for fk in contract['foreign_keys']:
        actual = next(f for f in inspector.get_foreign_keys(fk['table'], schema='public')
                      if f['constrained_columns'] == fk['columns'])
        if actual.get('options', {}).get('ondelete', 'NO ACTION') != _delete_rule(fk):
            raise SchemaPrerequisiteError(f'Post-migration FK delete action mismatch: {fk["table"]}')
    if plan.optional_tables:
        metadata = target_metadata(optional_tables=plan.optional_tables)
        for name in plan.optional_tables:
            expected_columns = metadata.tables['public.'+name].columns
            actual_columns = inspector.get_columns(name, schema='public')
            if [c['name'] for c in actual_columns] != list(expected_columns.keys()):
                raise SchemaPrerequisiteError(f'Optional fields mismatch: {name}')
            for col in expected_columns:
                expected_type = str(col.type.compile(dialect=bind.dialect))
                if _type_signature(types[name, col.name]) != _type_signature(expected_type):
                    raise SchemaPrerequisiteError(f'Optional type mismatch: {name}.{col.name}')
            if bind.execute(sa.text(f'SELECT count(*) FROM public.{_q(name)}')).scalar_one() != 0:
                raise SchemaPrerequisiteError(f'Unexpected optional rows: {name}')
            actual = {(tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns']), f.get('options', {}).get('ondelete', 'NO ACTION'))
                      for f in inspector.get_foreign_keys(name, schema='public')}
            expected_optional_fks = {(tuple(c), t, tuple(tc), rule) for table, c, t, tc, rule in OPTIONAL_FKS if table == name}
            if actual != expected_optional_fks:
                raise SchemaPrerequisiteError(f'Optional FK mismatch: {name}')
    invalid = bind.execute(sa.text("SELECT count(*) FROM pg_constraint WHERE connamespace IN ('public'::regnamespace,'news'::regnamespace) AND NOT convalidated")).scalar_one()
    if invalid:
        raise SchemaPrerequisiteError('Unvalidated constraints remain')
    # Catalog views are allowed; no compatibility aliases may survive.
    views = {(schema, n) for schema in ('public', 'news') for n in inspector.get_view_names(schema=schema)}
    if views - {('public', 'list_table'), ('public', 'list_column')}:
        raise SchemaPrerequisiteError('Legacy compatibility views remain')
    return {'tables': len(expected),
            'baseline_fields': sum(len(t['columns']) for t in contract['tables']),
            'fields': sum(len(t['columns']) for t in contract['tables']) + sum(len(COLUMN_COMMENTS[n]) for n in plan.optional_tables),
            'baseline_foreign_keys': len(expected_fks),
            'foreign_keys': len(expected_fks) + sum(table in plan.optional_tables for table, *_ in OPTIONAL_FKS),
            'fingerprints': digests}


def migrate(bind: sa.Connection, *, archive_path: str | Path, archive_sha256: str,  # noqa: PLR0912
            historical_timezone: str, expected_source_fingerprints: dict[str, str],
            source_snapshot: dict, optional_tables: tuple[str, ...] = OPTIONAL_TABLE_NAMES, allow_live: bool = False) -> dict:
    """Apply atomically inside an existing caller-owned transaction/savepoint.

    Locks cover the read/verify/drop window; a nested transaction rolls all DDL
    back even if the caller catches an exception and later commits its outer
    transaction. Live endpoints require an explicit switch as well as both
    approved-backup and archive-source fingerprint gates.
    """
    if not bind.in_transaction():
        raise SchemaPrerequisiteError('A caller-owned transaction is required')
    assert_rehearsal(bind, allow_live=allow_live)
    with bind.begin_nested():
        bind.execute(sa.text("SET LOCAL lock_timeout='5s'"))
        bind.execute(sa.text('SELECT pg_advisory_xact_lock(20261025, 27)'))
        # Fail before constructing LOCK statements for absent/replaced tables.
        if _inventory(bind) != SOURCE_TABLES:
            raise SchemaPrerequisiteError('Expected original 47-table inventory')
        bind.exec_driver_sql('LOCK TABLE '+','.join(_qualified(n) for n in sorted(SOURCE_TABLES))+' IN ACCESS EXCLUSIVE MODE')
        verify_source_snapshot(bind, source_snapshot, allow_live=allow_live)
        plan = preflight(bind, historical_timezone=historical_timezone,
                         optional_tables=optional_tables, allow_live=allow_live)
        if plan.source_fingerprints != expected_source_fingerprints:
            raise SchemaPrerequisiteError('Explicit source fingerprint gate does not match all 47 tables')
        _verify_archive(plan, archive_path, archive_sha256)
        inspector = sa.inspect(bind)
        views = {(schema, name) for schema in ('news', 'public') for name in inspector.get_view_names(schema=schema)}
        if views - {('public', 'list_column'), ('public', 'list_table')}:
            raise SchemaPrerequisiteError('Unexpected views; resolve dependencies before migrating')
        # Drop only explicit outgoing constraints on tables that are retired.
        # Foundation FKs remain and follow table/column renames automatically.
        for name in sorted({f'public.{n}' for n in PUBLIC_BUSINESS} | {f'news.{n}' for n in NEWS_TABLES}):
            schema, table = name.split('.')
            for fk in inspector.get_foreign_keys(table, schema=schema):
                bind.exec_driver_sql(f'ALTER TABLE {_qualified(name)} DROP CONSTRAINT {_q(fk["name"])} RESTRICT')
        for target, old in BASE_TABLES.items():
            if target != old:
                bind.exec_driver_sql(f'ALTER TABLE public.{_q(old)} RENAME TO {_q(target)}')
            spec = next(t for t in _contract()['tables'] if t['name'] == target)
            for col in spec['columns']:
                oldcol = col['old_name'] or col['name']
                if oldcol != col['name']:
                    bind.exec_driver_sql(f'ALTER TABLE public.{_q(target)} RENAME COLUMN {_q(oldcol)} TO {_q(col["name"])}')
        for name in sorted({f'public.{n}' for n in PUBLIC_BUSINESS} | {f'news.{n}' for n in NEWS_TABLES}):
            schema, table = name.split('.')
            bind.exec_driver_sql(f'DROP TABLE {_qualified(name)} RESTRICT')
        metadata = target_metadata(optional_tables=optional_tables)
        metadata.create_all(bind, checkfirst=False)
        for name, rows in plan.target.items():
            if name not in BASE_TABLES and rows:
                bind.execute(metadata.tables['public.'+name].insert(), rows)
        _constraints(bind, optional_tables=optional_tables)
        apply_menu_changes(bind, plan.menu_changes)
        apply_schema_comments(bind, optional_tables=optional_tables, allow_live=allow_live)
        # Preserve explicit basket IDs without letting subsequent inserts collide.
        bind.exec_driver_sql("SELECT setval(pg_get_serial_sequence('public.basket_items','id'), coalesce((SELECT max(id) FROM public.basket_items),1), EXISTS(SELECT 1 FROM public.basket_items))")
        report = verify_target(bind, plan)
        report['access'] = verify_access_contract(bind, plan.access_contract, optional_tables)
        return report
