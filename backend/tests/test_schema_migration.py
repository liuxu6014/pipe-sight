"""Pure preservation tests and opt-in PostgreSQL rehearsal (always rolled back)."""

# pytest supplies fixture arguments; literal counts express the frozen contract.
# ruff: noqa: ANN001, ANN201, ANN202, PLR2004

import importlib.util
import json
import os
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app import schema_migration as migration
from app.schema_contract import SchemaPrerequisiteError, load_contract


@pytest.fixture
def source():
    rows = {name: [] for name in migration.SOURCE_TABLES}
    stamp = datetime(2026, 10, 14, 19, 45, 56)
    rows['news.domains'] = [{'domain_id': 11, 'domain_name': '油气管网', 'user_id': None,
                                'filter_prompts': None, 'remark': '真实旧描述',
                                'create_time': stamp, 'update_time': stamp}]
    rows['public.prompt_versions'] = [{'prompt_id': 'filter-1', 'scene': 'data-filter',
                                           'status': 'published', 'system_prompt': '原始过滤提示词',
                                           'user_prompt': '{{body}} / {{title}}'}]
    rows['public.news_articles'] = [{'article_id': 'news-1', 'title': '真实标题',
                                        'article_type': 'wechat', 'source_id': None, 'source_name': '真实公众号',
                                        'canonical_url': 'https://example.org/article/1',
                                        'body': '实际正文\n第二段', 'author_text': None,
                                        'published_time': datetime(2024, 4, 15, 12, 0, 1),
                                        'published_at': stamp, 'permission_scope': 'public',
                                        'metadata_json': {}, 'create_time': stamp, 'update_time': stamp}]
    rows['public.papers'] = [{'paper_id': 'paper-1', 'title': 'Original paper', 'source_id': None,
                                 'canonical_url': 'https://doi.org/10.1234/ABC', 'doi': 'https://doi.org/10.1234/ABC',
                                 'doi_normalized': None, 'publication_year': 2024,
                                 'metadata_json': {'original_date': '2024-06'},
                                 'authors': 'A; B', 'journal': 'Journal', 'abstract_text': 'Actual abstract',
                                 'permission_scope': 'public', 'published_at': stamp,
                                 'create_time': stamp, 'update_time': stamp}]
    rows['public.template_versions'] = [{'template_id': 'template-1', 'name': '实际模板',
                                             'description': '原描述', 'report_type': 'research-demand',
                                             'sections': [{'title': '原章节', 'words': 1200}],
                                             'status': 'published', 'create_time': stamp, 'update_time': stamp}]
    return rows


def plan(source, **kwargs):
    return migration.build_plan(source, historical_timezone='Asia/Shanghai', **kwargs)


def test_contract_is_frozen_and_business_ddl_matches_all_fields():
    contract = load_contract('v1')
    metadata = migration.target_metadata()
    for table in contract['tables']:
        if table['name'] in migration.BASE_TABLES:
            continue
        actual = metadata.tables['public.' + table['name']]
        assert list(actual.c.keys()) == [c['name'] for c in table['columns']]
        assert {c.name: c.nullable for c in actual.c} == {c['name']: c['nullable'] for c in table['columns']}
        assert str(sa.schema.CreateTable(actual).compile(dialect=postgresql.dialect()))
    assert len(metadata.tables) == 13
    assert len(migration.target_metadata(optional_tables=migration.OPTIONAL_TABLE_NAMES).tables) == 15


def test_preserves_real_content_prompt_and_unconfigured_templates(source):
    result = plan(source)
    article = result.target['news_articles'][0]
    old = source['public.news_articles'][0]
    assert article['content'] == old['body']
    assert article['published_at'].replace(tzinfo=None) == old['published_time']
    assert article['published_at'].replace(tzinfo=None) != old['published_at']
    assert article['author'] is None
    assert result.target['data_sources'][0]['name'] == '真实公众号'
    assert result.target['data_sources'][0]['type'] == 'wechat'
    assert result.target['data_sources'][0]['is_enabled'] is False
    assert result.target['data_sources'][0]['url'] == old['canonical_url']
    paper = result.target['papers'][0]
    assert paper['published_date'] == '2024-06'
    assert paper['doi'] == '10.1234/abc'
    assert paper['abstract'] == 'Actual abstract'
    assert not {'content', 'content_zh', 'full_text_url'} & paper.keys()
    assert '原始过滤提示词' in result.target['categories'][0]['prompt']
    assert '{{body}}' in result.target['categories'][0]['prompt']
    assert not result.target['categories'][0]['is_enabled']
    template = result.target['templates'][0]
    assert template['model_id'] is template['image_model_id'] is None
    assert template['sections'] == source['public.template_versions'][0]['sections']
    assert json.loads(template['prompt'])['sections'] == template['sections']
    assert result.target['ai_models'] == []


@pytest.mark.parametrize('value', ['2024', '2024-02', '2024-02-29'])
def test_date_precision_is_not_invented(value):
    assert migration.paper_date({'metadata_json': {'original_date': value}, 'publication_year': 2024}) == value


@pytest.mark.parametrize('value', ['2023-02-29', '2024-13', '2024-00', '2024-01-00', '2024-1', '2024-01-01T00:00:00', '0000'])
def test_invalid_source_dates_refused(value):
    with pytest.raises(SchemaPrerequisiteError, match='date'):
        migration.paper_date({'metadata_json': {'original_date': value}})


def test_no_source_date_does_not_fall_back_to_approval_time():
    assert migration.paper_date({'published_at': '2026-10-14'}) is None
    with pytest.raises(SchemaPrerequisiteError, match='Conflicting'):
        migration.paper_date({'publication_year': 2023, 'metadata_json': {'original_date': '2024-02'}})


@pytest.mark.parametrize('table', ['public.news_articles', 'public.papers'])
def test_private_content_refused_before_any_write(source, table):
    source[table][0]['permission_scope'] = 'private'
    with pytest.raises(SchemaPrerequisiteError, match='Private'):
        plan(source)


@pytest.mark.parametrize('table', ['public.reports', 'public.knowledge_files', 'public.ai_models',
                                   'public.model_routes', 'news.articles', 'news.topics',
                                   'public.report_versions', 'public.model_calls', 'public.ai_chat_config'])
def test_unimplemented_nonempty_entity_refused(source, table):
    source[table].append({'id': 'must-not-disappear'})
    with pytest.raises(SchemaPrerequisiteError, match='Unmapped nonempty'):
        plan(source)


def test_local_paper_fulltext_refused(source):
    source['public.papers'][0]['metadata_json']['full_text_imported'] = True
    with pytest.raises(SchemaPrerequisiteError, match='full text'):
        plan(source)


def test_ambiguous_prompt_and_source_refs_refused(source):
    source['public.prompt_versions'].append(deepcopy(source['public.prompt_versions'][0]))
    with pytest.raises(SchemaPrerequisiteError, match='ambiguous'):
        plan(source)
    source['public.prompt_versions'].pop()
    source['public.news_articles'][0]['source_id'] = 'absent'
    with pytest.raises(SchemaPrerequisiteError, match='source reference'):
        plan(source)


def test_missing_content_identity_and_duplicates_refused(source):
    source['public.news_articles'][0]['source_name'] = ''
    with pytest.raises(SchemaPrerequisiteError, match='source name'):
        plan(source)
    source['public.news_articles'][0]['source_name'] = 'Real'
    row = deepcopy(source['public.news_articles'][0])
    row['article_id'] = 'news-2'
    source['public.news_articles'].append(row)
    with pytest.raises(SchemaPrerequisiteError, match='Duplicate target unique'):
        plan(source)


def test_paper_url_dedup_only_when_doi_is_absent(source):
    other = deepcopy(source['public.papers'][0])
    other['paper_id'] = 'paper-2'
    other['doi'] = '10.1234/distinct'
    source['public.papers'].append(other)
    assert len(plan(source).target['papers']) == 2
    for row in source['public.papers']:
        row['doi'] = None
    with pytest.raises(SchemaPrerequisiteError, match='Duplicate target unique'):
        plan(source)


def test_unmapped_basket_type_and_orphan_refused(source):
    stamp = source['public.news_articles'][0]['create_time']
    row = {'saved_item_id': 2, 'item_type': 'unknown', 'item_id': 'missing', 'user_id': 2,
               'action': 'basket', 'create_time': stamp}
    source['public.user_saved_items'] = [row]
    with pytest.raises(SchemaPrerequisiteError, match='basket item type'):
        plan(source)
    row['item_type'] = 'paper'
    with pytest.raises(SchemaPrerequisiteError, match='Orphan target'):
        plan(source)


def test_archive_preserves_retired_events_and_detects_stale_content(source, tmp_path):
    source['public.content_review_events'] = [{'event_id': 'old-review', 'snapshot_json': {'title': '原文'}}]
    result = plan(source)
    path = tmp_path / 'retirement.json'
    digest = migration.archive_plan(result, path)
    payload = json.loads(path.read_bytes())
    assert payload['retired_business_rows']['public.content_review_events'] == source['public.content_review_events']
    assert path.stat().st_mode & 0o077 == 0
    assert 'public.sys_user' not in payload['retired_business_rows']
    migration._verify_archive(result, path, digest)
    with pytest.raises(FileExistsError):
        migration.archive_plan(result, path)
    source['public.news_articles'][0]['body'] = 'Changed after archive'
    with pytest.raises(SchemaPrerequisiteError, match='stale'):
        migration._verify_archive(plan(source), path, digest)


def test_archive_hash_and_mode_are_required(source, tmp_path):
    result = plan(source)
    path = tmp_path / 'retirement.json'
    digest = migration.archive_plan(result, path)
    with pytest.raises(SchemaPrerequisiteError, match='SHA-256'):
        migration._verify_archive(result, path, '0' * 64)
    path.chmod(0o644)
    with pytest.raises(SchemaPrerequisiteError, match='private'):
        migration._verify_archive(result, path, digest)


def test_fingerprint_ignores_row_order_not_content_or_timezone():
    stamp = datetime(2026, 10, 25, tzinfo=timezone.utc)
    assert migration.fingerprint([{'a': 1}, {'a': 2}]) == migration.fingerprint([{'a': 2}, {'a': 1}])
    assert migration.fingerprint([{'a': 1}]) != migration.fingerprint([{'a': 1}, {'a': 1}])
    assert migration.fingerprint([{'t': stamp}]) == migration.fingerprint([{'t': stamp.astimezone(ZoneInfo('Asia/Shanghai'))}])


def test_real_endpoints_rejected_without_even_a_query():
    class NoSQL:
        dialect = SimpleNamespace(name='postgresql')
        engine = SimpleNamespace(url=sa.URL.create('postgresql', host='172.16.4.183', port=5432, database='pipesight'))
        def execute(self, *args, **kwargs):
            pytest.fail('A real endpoint must be rejected before SQL')
    with pytest.raises(SchemaPrerequisiteError, match='allow_live'):
        migration.assert_rehearsal(NoSQL())


def test_revision_requires_explicit_options_and_has_no_lossy_downgrade(monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/20261025_compact_schema.py'
    spec = importlib.util.spec_from_file_location('compact_revision', path)
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    monkeypatch.setattr(revision.context, 'get_x_argument', lambda **kwargs: {})
    with pytest.raises(RuntimeError, match='required'):
        revision.upgrade()
    with pytest.raises(RuntimeError, match='backup'):
        revision.downgrade()
    assert revision.down_revision == '20261025_retire_processing_views'


def menu_rows():
    rows = [{'id': 4, 'parent_id': 0, 'name': 'AI管理', 'path': 'ai', 'component': None, 'type': 'M', 'permissions': ''},
            {'id': 1300, 'parent_id': 0, 'name': '管网情报', 'path': 'pipeline', 'component': None, 'type': 'M', 'permissions': ''}]
    for identity, path, name in [(2002, 'intelligence', '情报审核'), (2005, 'task', '采集任务'),
                                  (2006, 'report', '报告'), (2008, 'template', '模板'),
                                  (2009, 'model', '模型与Prompt')]:
        rows.append({'id': identity, 'parent_id': 1300, 'name': name, 'path': path,
                         'component': 'pipeline/' + path + '/index', 'type': 'C', 'permissions': ''})
    for identity, (permission, parent, kind) in migration.RETIRED_MENU_IDENTITIES.items():
        path, component = (('chat', 'ai/chat/index') if identity == 119 else
                           ('governance', 'pipeline/governance/index')) if kind == 'C' else ('', None)
        rows.append({'id': identity, 'parent_id': parent, 'name': '旧功能', 'path': path,
                         'component': component, 'type': kind, 'permissions': permission})
    rows.append({'id': 2025, 'parent_id': 2005, 'name': '采集与交接', 'path': '', 'component': None,
                     'type': 'F', 'permissions': 'pipeline:task:run'})
    rows.append({'id': 9000, 'parent_id': 4, 'name': '用户自有模型入口', 'path': 'model', 'component': 'ai/model/index',
                     'type': 'C', 'permissions': 'ai:model:list'})
    return rows


def test_menu_plan_deletes_only_verified_identities_and_exact_role_links():
    rows = menu_rows()
    before = deepcopy(rows)
    links = [{'role_id': 2, 'menu_id': n} for n in (119, 1301, 2015, 2021, 2028, 2009, 9000)]
    projected = migration.project_menus(rows, links)
    assert rows == before
    assert {r['id'] for r in projected['archive']['retired_menus']} == set(migration.RETIRED_MENU_IDENTITIES)
    by_id = {r['id']: r for r in projected['menus']}
    assert by_id[2009]['name'] == '模型与类别提示词'
    assert by_id[2002]['name'] == '情报查询' and by_id[2002]['path'] == 'intelligence'
    assert by_id[2025]['name'] == '运行、停止与失败重试'
    assert by_id[9000] == next(r for r in rows if r['id'] == 9000)
    assert projected['role_menus'] == [{'role_id': 2, 'menu_id': n} for n in (2009, 9000)]


@pytest.mark.parametrize('identity,field,value', [(1301, 'component', 'system/menu/index'),
    (1302, 'permissions', 'system:menu:edit'), (2015, 'parent_id', 1),
    (2021, 'type', 'C'), (2026, 'permissions', 'pipeline:intel:list'),
    (119, 'component', 'ai/model/index'), (2009, 'component', 'ai/chat/index')])
def test_repurposed_menu_id_is_preflight_failure(identity, field, value):
    rows = menu_rows()
    next(r for r in rows if r['id'] == identity)[field] = value
    with pytest.raises(SchemaPrerequisiteError, match=r'identity|route|permission'):
        migration.project_menus(rows, [])


def test_filter_is_located_by_real_component_or_full_path_without_deleting_unknown_children():
    rows = menu_rows()
    rows.append({'id': 8888, 'parent_id': 1300, 'name': '过滤', 'path': 'filter', 'component': 'pipeline/filter/index',
                     'type': 'C', 'permissions': 'pipeline:filter:list'})
    assert 8888 in {r['id'] for r in migration.project_menus(rows, [])['archive']['retired_menus']}
    rows.append({'id': 8889, 'parent_id': 8888, 'name': '用户自定义操作', 'path': '', 'component': None,
                     'type': 'F', 'permissions': 'user:custom:operate'})
    with pytest.raises(SchemaPrerequisiteError, match='Unapproved child'):
        migration.project_menus(rows, [])


@pytest.mark.parametrize('selection', [True, False, ('chat_settings',), ('model_calls', 'model_calls'), 'model_calls'])
def test_optional_selection_is_exact_and_rejects_retired_chat(source, selection):
    with pytest.raises(SchemaPrerequisiteError, match='Optional tables'):
        plan(source, optional_tables=selection)


@pytest.mark.parametrize('selection,total,fields', [((), 27, 317), (('model_calls',), 28, 327),
    (('report_versions',), 28, 330), (migration.OPTIONAL_TABLE_NAMES, 29, 340)])
def test_exact_optional_sets_have_exact_target_counts(source, selection, total, fields):
    result = plan(source, optional_tables=selection)
    assert result.summary['physical_table_count'] == total
    assert result.summary['field_count'] == fields
    assert set(migration.target_metadata(optional_tables=selection).tables) == {
        'public.' + n for n in result.target if n not in migration.BASE_TABLES} | {'public.' + n for n in selection}


@pytest.mark.skipif(os.environ.get('PIPESIGHT_COMPACT_REHEARSE') != '1', reason='Explicit isolated rehearsal opt-in only')
@pytest.mark.parametrize('optional_tables', [migration.OPTIONAL_TABLE_NAMES, ()])
def test_real_pg18_rehearsal_rolls_back_all_ddl_and_preserves_data(tmp_path, optional_tables, monkeypatch):  # noqa: PLR0915
    root = Path(__file__).resolve().parents[2] / '.runtime/schema-rollout-ythNjXpI'
    info = json.loads((root / 'rehearsal-connection.json').read_text())
    assert info['host'] == '127.0.0.1' and int(info['port']) == 19432 and info['dbname'] == 'pipesight_rehearsal'
    # Never print docker inspect's Env, which includes a container credential.
    inspect = subprocess.run(['docker', 'inspect', '--format', '{{json .Config.Labels}}',
                              'pipesight-schema-rehearsal-ythnjxpi'], check=True, capture_output=True)
    assert json.loads(inspect.stdout)['pipesight.schema-rollout'] == 'ythNjXpI'
    ports = subprocess.run(['docker', 'inspect', '--format', '{{json .NetworkSettings.Ports}}',
                            'pipesight-schema-rehearsal-ythnjxpi'], check=True, capture_output=True)
    assert {'HostIp': '127.0.0.1', 'HostPort': '19432'} in json.loads(ports.stdout)['5432/tcp']
    url = sa.URL.create('postgresql+psycopg2', username=info['user'], password=info['password'],
                        host=info['host'], port=info['port'], database=info['dbname'])
    engine = sa.create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as bind:
            outer = bind.begin()
            try:
                original = migration.preflight(bind, historical_timezone='Asia/Shanghai', optional_tables=optional_tables)
                for sql, reason in [
                    ('GRANT SELECT ON public.ai_models TO PUBLIC', 'Third-party'),
                    ('ALTER TABLE public.ai_models OWNER TO pg_read_all_data', 'Migration role'),
                ]:
                    with bind.begin_nested() as privilege_probe:
                        bind.exec_driver_sql(sql)
                        with pytest.raises(SchemaPrerequisiteError, match=reason):
                            migration.preflight(bind, historical_timezone='Asia/Shanghai', optional_tables=optional_tables)
                        privilege_probe.rollback()
                archive = tmp_path / 'retirement.json'
                digest = migration.archive_plan(original, archive)
                kwargs = {'archive_path': archive, 'archive_sha256': digest,
                              'historical_timezone': 'Asia/Shanghai', 'optional_tables': optional_tables,
                              'source_snapshot': json.loads((root / 'database-before.json').read_bytes()),
                              'expected_source_fingerprints': original.source_fingerprints}
                wrong = dict(original.source_fingerprints, **{'public.news_articles': 'bad'})
                with pytest.raises(SchemaPrerequisiteError, match='fingerprint gate'):
                    migration.migrate(bind, **dict(kwargs, expected_source_fingerprints=wrong))
                assert migration._inventory(bind) == migration.SOURCE_TABLES
                verify = migration.verify_target
                def fail_after_ddl(connection, checked_plan):
                    verify(connection, checked_plan)
                    raise SchemaPrerequisiteError('Injected failure after all DDL and data checks')
                with monkeypatch.context() as patch:
                    patch.setattr(migration, 'verify_target', fail_after_ddl)
                    with pytest.raises(SchemaPrerequisiteError, match='Injected failure'):
                        migration.migrate(bind, **kwargs)
                restored = migration.preflight(bind, historical_timezone='Asia/Shanghai', optional_tables=optional_tables)
                assert restored.source_fingerprints == original.source_fingerprints
                report = migration.migrate(bind, **kwargs)
                assert report['tables'] == 27 + len(optional_tables)
                assert report['baseline_fields'] == 317 and report['baseline_foreign_keys'] == 31
                assert report['fields'] == 317 + sum(len(migration.COLUMN_COMMENTS[n]) for n in optional_tables)
                assert report['foreign_keys'] == 31 + sum(t in optional_tables for t, *_ in migration.OPTIONAL_FKS)
                assert bind.execute(sa.text('SELECT count(*) FROM public.news_articles')).scalar_one() == 6
                assert bind.execute(sa.text('SELECT count(*) FROM public.papers')).scalar_one() == 3
                assert bind.execute(sa.text('SELECT count(*) FROM public.templates WHERE model_id IS NULL')).scalar_one() == 6
                assert bind.execute(sa.text('SELECT count(*) FROM public.ai_models')).scalar_one() == 0
                assert bind.execute(sa.text("SELECT count(*) FROM public.categories WHERE prompt LIKE '%{{body}}%'")).scalar_one() == 1
                assert {r[0] for r in bind.execute(sa.text('SELECT published_date FROM public.papers'))} == {'2024-03', '2020-11', '2024-03-18'}
                # Existing basket ID and identity advance independently.
                assert bind.execute(sa.text("SELECT pg_get_serial_sequence('basket_items','id')")).scalar_one()
                # The server enforces the contract, including impossible dates,
                # source existence and exactly one basket source.
                for sql in [
                    "UPDATE public.papers SET published_date='2023-02-29'",
                    "UPDATE public.news_articles SET source_id='missing'",
                    "UPDATE public.basket_items SET paper_id=NULL",
                    "UPDATE public.categories SET is_enabled=true,model_id=NULL",
                ]:
                    with pytest.raises(sa.exc.DBAPIError), bind.begin_nested():
                        bind.execute(sa.text(sql))
            finally:
                outer.rollback()
            restored = migration.preflight(bind, historical_timezone='Asia/Shanghai', optional_tables=optional_tables)
            assert restored.source_fingerprints == original.source_fingerprints
    finally:
        engine.dispose()
