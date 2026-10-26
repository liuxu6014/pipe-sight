"""Pure numeric migration plans; no database, files, or production writes."""

import json
from copy import deepcopy
from datetime import time
from hashlib import sha256
from typing import Any

import pytest

from app import business_ids as ids
from app import numeric_id_migration as migration
from app.numeric_id_migration import build_plan

PlanInput = tuple[dict[str, list[dict]], list[dict]]


@pytest.fixture
def numeric_plan_input() -> tuple[dict[str, list[dict]], list[dict]]:
    """Only schema-confirmed references; identical old IDs test typed resolution."""
    selected = [{'type': kind, 'id': 'shared-old'} for kind in ('article', 'paper', 'file')]
    snapshot = {
        'template': {
            'id': 'template-old',
            'image_model_id': 100,
            'sections': [{'id': 'template-old', 'title': 'Local section', 'citationIds': [1]}],
            'image_config': {'count': 2, 'prompt': 'template-old'},
        },
        'request': {'template_id': 'template-old', 'report_id': 'report-old', 'selected_item_ids': selected},
        'model': {'id': 99, 'code': 'shared-old', 'parameters': {'max_tokens': 2048}},
        'image_model': {'id': 100},
        'request_fingerprint': 'frozen-fingerprint',
    }
    rows = {table: [] for table in ids.BUSINESS_ID_TABLES}
    rows.update(
        {
            'sys_user': [{'id': 7, 'username': 'unchanged'}],
            'ai_models': [{'id': 99}, {'id': 100}],
            'categories': [{'id': 'category-old', 'model_id': 99}],
            'data_sources': [
                {
                    'id': 'source-old',
                    'model_id': 99,
                    'config': {
                        'source_id': 'source-old',
                        'external': {'id': 'shared-old', 'source_id': 'source-old'},
                        'query': 'source-old shared-old',
                        'retry': {'max_retries': 3},
                    },
                }
            ],
            'collection_runs': [
                {'id': 'run-root', 'source_id': 'source-old', 'parent_id': None},
                {'id': 'run-retry', 'source_id': 'source-old', 'parent_id': 'run-root'},
            ],
            'news_articles': [{'id': 'shared-old', 'source_id': 'source-old', 'category_id': 'category-old'}],
            'papers': [{'id': 'shared-old', 'source_id': None, 'category_id': 'category-old'}],
            'knowledge_files': [{'id': 'shared-old', 'user_id': 7}],
            'templates': [
                {
                    'id': 'template-old',
                    'model_id': 99,
                    'image_model_id': 100,
                    'sections': deepcopy(snapshot['template']['sections']),
                    'image_config': deepcopy(snapshot['template']['image_config']),
                }
            ],
            'reports': [{'id': 'report-old', 'template_id': 'template-old', 'user_id': 7}],
            'digest_schedules': [
                {
                    'id': 'schedule-old',
                    'template_id': 'template-old',
                    'user_id': 7,
                    'selection_config': {
                        'source_ids': ['source-old'],
                        'category_ids': ['category-old'],
                        'category_names': ['category-old'],
                        'keywords': ['shared-old'],
                    },
                    'generation_config': {
                        'requirements': 'source-old shared-old',
                        'outline': [{'id': 1, 'title': 'shared-old'}],
                    },
                }
            ],
            'generation_tasks': [
                {
                    'id': 'task-old',
                    'report_id': 'report-old',
                    'schedule_id': 'schedule-old',
                    'request_id': 'schedule:schedule-old:2026-10-25T00:00:00+00:00',
                    'config_snapshot': deepcopy(snapshot),
                    'materials': [
                        {
                            'type': 'article',
                            'id': 'shared-old',
                            'title': 'shared-old',
                            'content': 'source-old',
                            'source': {'source_id': 'source-old', 'url': 'https://example.invalid/shared-old'},
                        },
                        {
                            'type': 'paper',
                            'id': 'shared-old',
                            'content': 'shared-old',
                            'source': {'doi': '10.1234/shared-old'},
                        },
                        {
                            'type': 'file',
                            'id': 'shared-old',
                            'content': 'shared-old',
                            'source': {'filename': 'shared-old.txt'},
                        },
                    ],
                }
            ],
            'model_calls': [{'id': 'call-old', 'task_id': 'task-old', 'model_id': 99}],
            'report_assets': [
                {
                    'id': 'asset-old',
                    'task_id': 'task-old',
                    'report_id': 'report-old',
                    'model_id': 100,
                    'config_snapshot': {'model': {'id': 100}, 'image_config': {'prompt': 'shared-old'}},
                }
            ],
            'report_versions': [
                {
                    'id': 15,
                    'report_id': 'report-old',
                    'operator_id': 7,
                    'model_snapshot': deepcopy(snapshot),
                    'sections': [{'id': 1, 'citationIds': [1], 'content': 'shared-old'}],
                    'citations': [{'id': 1, 'title': 'shared-old', 'url': 'https://example.invalid/shared-old'}],
                }
            ],
            'basket_items': [
                {
                    'id': 16,
                    'user_id': 7,
                    'article_id': 'shared-old',
                    'paper_id': None,
                    'file_id': None,
                    'report_id': None,
                }
            ],
        }
    )
    foreign_keys = []

    def fk(table: str, columns: list[str], target: str, target_columns: list[str]) -> None:
        foreign_keys.append(
            {
                'table': table,
                'columns': columns,
                'target': target,
                'target_columns': target_columns,
                'name': 'fk_' + table + '_' + '_'.join(columns),
                'definition': f'FOREIGN KEY ({", ".join(columns)}) REFERENCES {target}({", ".join(target_columns)})',
            }
        )

    for table, column, target in (
        ('collection_runs', 'source_id', 'data_sources'),
        ('news_articles', 'source_id', 'data_sources'),
        ('news_articles', 'category_id', 'categories'),
        ('papers', 'source_id', 'data_sources'),
        ('papers', 'category_id', 'categories'),
        ('reports', 'template_id', 'templates'),
        ('digest_schedules', 'template_id', 'templates'),
        ('generation_tasks', 'report_id', 'reports'),
        ('generation_tasks', 'schedule_id', 'digest_schedules'),
        ('model_calls', 'task_id', 'generation_tasks'),
        ('report_assets', 'report_id', 'reports'),
        ('report_versions', 'report_id', 'reports'),
        ('basket_items', 'article_id', 'news_articles'),
        ('basket_items', 'paper_id', 'papers'),
        ('basket_items', 'file_id', 'knowledge_files'),
        ('basket_items', 'report_id', 'reports'),
        ('knowledge_files', 'user_id', 'sys_user'),
        ('model_calls', 'model_id', 'ai_models'),
    ):
        fk(table, [column], target, ['id'])
    fk('collection_runs', ['parent_id', 'source_id'], 'collection_runs', ['id', 'source_id'])
    fk('report_assets', ['task_id', 'report_id'], 'generation_tasks', ['id', 'report_id'])
    return rows, foreign_keys


def build_numeric_plan(numeric_plan_input: PlanInput) -> Any:
    rows, foreign_keys = numeric_plan_input
    return build_plan(rows, foreign_keys)


@pytest.fixture
def minimal_plan_input(numeric_plan_input: PlanInput) -> PlanInput:
    rows, foreign_keys = deepcopy(numeric_plan_input)
    json_fields = {
        'generation_tasks': ('materials', 'config_snapshot'),
        'report_versions': ('sections', 'citations', 'model_snapshot'),
        'report_assets': ('config_snapshot',),
        'digest_schedules': ('selection_config', 'generation_config'),
        'templates': ('sections', 'image_config'),
        'data_sources': ('config',),
    }
    for table, fields in json_fields.items():
        for row in rows[table]:
            for field in fields:
                row.pop(field, None)
    return rows, foreign_keys


def test_numeric_plan_maps_all_business_tables_to_globally_unique_bigints(minimal_plan_input: PlanInput) -> None:
    rows, _ = minimal_plan_input
    plan = build_numeric_plan(minimal_plan_input)
    values = []
    for table in ids.BUSINESS_ID_TABLES:
        for old, new in zip(rows[table], plan.target_rows[table], strict=True):
            value = plan.mappings[table][str(old['id'])]
            assert type(value) is int and 1 <= value <= ids.MAX_BIGINT
            assert type(new['id']) is int and new['id'] == value
            values.append(value)
    assert len(values) == len(set(values))


def test_numeric_plan_does_not_mutate_input_or_existing_native_ids(minimal_plan_input: PlanInput) -> None:
    before = deepcopy(minimal_plan_input)
    plan = build_numeric_plan(minimal_plan_input)
    assert minimal_plan_input == before
    assert plan.target_rows['sys_user'] == before[0]['sys_user']
    assert plan.target_rows['ai_models'] == before[0]['ai_models']
    assert plan.target_rows['report_versions'][0]['id'] == before[0]['report_versions'][0]['id']
    assert plan.target_rows['basket_items'][0]['id'] == before[0]['basket_items'][0]['id']


def test_numeric_plan_remaps_real_fks_as_int_and_preserves_nullable_targets(minimal_plan_input: PlanInput) -> None:
    plan = build_numeric_plan(minimal_plan_input)
    mapped, rows = plan.mappings, plan.target_rows
    assert rows['news_articles'][0]['source_id'] == mapped['data_sources']['source-old']
    assert type(rows['news_articles'][0]['source_id']) is int
    assert rows['papers'][0]['source_id'] is None
    assert rows['collection_runs'][0]['parent_id'] is None
    assert rows['collection_runs'][1]['parent_id'] == mapped['collection_runs']['run-root']
    assert rows['collection_runs'][1]['source_id'] == mapped['data_sources']['source-old']
    assert rows['report_assets'][0]['task_id'] == mapped['generation_tasks']['task-old']
    assert rows['report_assets'][0]['report_id'] == mapped['reports']['report-old']
    assert rows['basket_items'][0]['article_id'] == mapped['news_articles']['shared-old']
    assert rows['basket_items'][0]['paper_id'] is None


def test_numeric_plan_material_and_request_refs_are_typed_decimal_strings(numeric_plan_input: PlanInput) -> None:
    plan = build_numeric_plan(numeric_plan_input)
    task = plan.target_rows['generation_tasks'][0]
    refs = task['config_snapshot']['request']['selected_item_ids']
    for material, reference, table in zip(
        task['materials'], refs, ('news_articles', 'papers', 'knowledge_files'), strict=True
    ):
        expected = str(plan.mappings[table]['shared-old'])
        assert type(material['id']) is str and material['id'] == expected
        assert type(reference['id']) is str and reference['id'] == expected
    assert task['materials'][0]['source']['source_id'] == str(plan.mappings['data_sources']['source-old'])
    assert task['config_snapshot']['template']['id'] == str(plan.mappings['templates']['template-old'])
    assert task['config_snapshot']['request']['template_id'] == str(plan.mappings['templates']['template-old'])
    assert task['config_snapshot']['request']['report_id'] == str(plan.mappings['reports']['report-old'])


def test_numeric_plan_digest_selection_and_version_snapshot_use_precise_paths(
    minimal_plan_input: PlanInput,
    numeric_plan_input: PlanInput,
) -> None:
    rows, _ = minimal_plan_input
    rows['digest_schedules'][0]['selection_config'] = deepcopy(
        numeric_plan_input[0]['digest_schedules'][0]['selection_config']
    )
    rows['report_versions'][0]['model_snapshot'] = {'template': {'id': 'template-old'}}
    plan = build_numeric_plan(minimal_plan_input)
    schedule = plan.target_rows['digest_schedules'][0]
    assert schedule['selection_config']['source_ids'] == [str(plan.mappings['data_sources']['source-old'])]
    assert schedule['selection_config']['category_ids'] == [str(plan.mappings['categories']['category-old'])]
    assert schedule['selection_config']['category_names'] == ['category-old']
    assert schedule['selection_config']['keywords'] == ['shared-old']
    assert plan.target_rows['report_versions'][0]['model_snapshot']['template']['id'] == str(
        plan.mappings['templates']['template-old']
    )


def test_numeric_plan_preserves_external_config_local_ids_and_user_text(numeric_plan_input: PlanInput) -> None:
    original, _ = numeric_plan_input
    plan = build_numeric_plan(numeric_plan_input)
    rows = plan.target_rows
    # Even an external source_id identical to a real old primary key is opaque.
    assert rows['data_sources'][0]['config'] == original['data_sources'][0]['config']
    for column in ('sections', 'image_config'):
        assert rows['templates'][0][column] == original['templates'][0][column]
    for column in ('sections', 'citations'):
        assert rows['report_versions'][0][column] == original['report_versions'][0][column]
    assert rows['digest_schedules'][0]['generation_config'] == original['digest_schedules'][0]['generation_config']
    task = rows['generation_tasks'][0]
    assert task['request_id'] == f'schedule:{plan.mappings["digest_schedules"]["schedule-old"]}:2026-10-25T00:00:00+00:00'
    assert task['materials'][0]['title'] == 'shared-old'
    assert task['materials'][0]['content'] == 'source-old'
    assert task['materials'][0]['source']['url'] == 'https://example.invalid/shared-old'
    assert task['materials'][1]['source']['doi'] == '10.1234/shared-old'
    assert task['materials'][2]['source']['filename'] == 'shared-old.txt'
    for key in ('model', 'image_model'):
        assert task['config_snapshot'][key] == original['generation_tasks'][0]['config_snapshot'][key]


def test_convert_columns_propagates_composite_fk_roles_without_converting_native_ids(
    minimal_plan_input: PlanInput,
) -> None:
    plan = build_numeric_plan(minimal_plan_input)
    assert plan.convert_columns['collection_runs', 'parent_id'] == 'collection_runs'
    assert plan.convert_columns['collection_runs', 'source_id'] == 'data_sources'
    assert plan.convert_columns['report_assets', 'task_id'] == 'generation_tasks'
    assert plan.convert_columns['report_assets', 'report_id'] == 'reports'
    assert plan.convert_columns['basket_items', 'article_id'] == 'news_articles'
    for key in (
        ('basket_items', 'id'),
        ('report_versions', 'id'),
        ('model_calls', 'model_id'),
        ('knowledge_files', 'user_id'),
    ):
        assert key not in plan.convert_columns


def test_plan_rewrite_audit_records_original_and_new_reference(minimal_plan_input: PlanInput) -> None:
    plan = build_numeric_plan(minimal_plan_input)
    expected = {
        'path': 'news_articles[0].source_id',
        'entity': 'data_sources',
        'old_id': 'source-old',
        'new_id': plan.mappings['data_sources']['source-old'],
    }
    assert expected in plan.rewrites


def test_duplicate_source_ids_are_rejected_without_mutating_input(minimal_plan_input: PlanInput) -> None:
    rows, foreign_keys = minimal_plan_input
    rows['papers'].append(deepcopy(rows['papers'][0]))
    before = deepcopy(rows)
    with pytest.raises(ValueError, match='Duplicate'):
        build_plan(rows, foreign_keys)
    assert rows == before


def test_dangling_real_fk_is_rejected_before_any_projection_can_be_applied(minimal_plan_input: PlanInput) -> None:
    rows, foreign_keys = minimal_plan_input
    rows['news_articles'][0]['source_id'] = 'not-a-source'
    before = deepcopy(rows)
    with pytest.raises(ValueError, match='Unmapped'):
        build_plan(rows, foreign_keys)
    assert rows == before


def test_conflicting_fk_roles_are_rejected(minimal_plan_input: PlanInput) -> None:
    rows, foreign_keys = minimal_plan_input
    foreign_keys.append(
        {
            'table': 'news_articles',
            'columns': ['source_id'],
            'target': 'categories',
            'target_columns': ['id'],
            'name': 'fk_conflicting_role',
            'definition': 'unused pure-plan text',
        }
    )
    with pytest.raises(ValueError, match='Conflicting'):
        build_plan(rows, foreign_keys)


def test_numeric_capacity_is_checked_before_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = {table: [] for table in ids.BUSINESS_ID_TABLES}
    rows['categories'] = [{'id': f'old-{i}'} for i in range(3)]
    monkeypatch.setattr(migration, 'MAX_BIGINT', 2)
    with pytest.raises(ValueError, match='capacity'):
        build_plan(rows, [])


def test_empty_business_tables_have_an_empty_shared_mapping() -> None:
    rows = {table: [] for table in ids.BUSINESS_ID_TABLES}
    plan = build_plan(rows, [])
    assert plan.mappings == {table: {} for table in ids.BUSINESS_ID_TABLES}
    assert plan.target_rows == rows
    assert plan.rewrites == []


@pytest.mark.parametrize('field', ['selected_item_ids', 'selectedItemIds'])
def test_typed_selected_item_objects_are_not_treated_as_scalar_ids(minimal_plan_input: PlanInput, field: str) -> None:
    rows, foreign_keys = minimal_plan_input
    rows['generation_tasks'][0]['config_snapshot'] = {
        'request': {
            field: [{'type': kind, 'id': 'shared-old'} for kind in ('article', 'paper', 'file')],
        }
    }
    plan = build_plan(rows, foreign_keys)
    selected = plan.target_rows['generation_tasks'][0]['config_snapshot']['request'][field]
    for item, table in zip(selected, ('news_articles', 'papers', 'knowledge_files'), strict=True):
        assert item['id'] == str(plan.mappings[table]['shared-old'])


def test_ambiguous_legacy_scalar_selection_is_rejected(minimal_plan_input: PlanInput) -> None:
    rows, foreign_keys = minimal_plan_input
    rows['generation_tasks'][0]['config_snapshot'] = {'request': {'selected_item_ids': ['shared-old']}}
    with pytest.raises(ValueError, match='ambiguous'):
        build_plan(rows, foreign_keys)


@pytest.mark.parametrize('external_id', ['source-old', 'external-only'])
def test_crawler_config_source_id_is_opaque_even_when_equal_to_real_old_id(
    minimal_plan_input: PlanInput,
    external_id: str,
) -> None:
    rows, foreign_keys = minimal_plan_input
    config = {'source_id': external_id, 'external': {'id': 'shared-old', 'sourceId': external_id}}
    rows['data_sources'][0]['config'] = deepcopy(config)
    plan = build_plan(rows, foreign_keys)
    assert plan.target_rows['data_sources'][0]['config'] == config
    assert not any(row['path'].startswith('data_sources[0].config') for row in plan.rewrites)


@pytest.mark.parametrize('kind,table', [('article', 'news_articles'), ('paper', 'papers'), ('file', 'knowledge_files')])
def test_citation_source_id_refers_to_typed_content_not_data_source(
    minimal_plan_input: PlanInput,
    kind: str,
    table: str,
) -> None:
    rows, foreign_keys = minimal_plan_input
    rows['report_versions'][0]['sections'] = [{'id': 1, 'citationIds': [1]}]
    rows['report_versions'][0]['citations'] = [{'id': 1, 'type': kind, 'sourceId': 'shared-old', 'title': 'keep title'}]
    plan = build_plan(rows, foreign_keys)
    version = plan.target_rows['report_versions'][0]
    assert version['citations'][0]['sourceId'] == str(plan.mappings[table]['shared-old'])
    assert version['citations'][0]['id'] == 1
    assert version['sections'] == [{'id': 1, 'citationIds': [1]}]


def test_existing_model_ids_parameters_and_text_are_not_business_id_references(minimal_plan_input: PlanInput) -> None:
    rows, foreign_keys = minimal_plan_input
    snapshot = {
        'model': {'id': 99, 'source_id': 'source-old', 'parameters': {'templateId': 'template-old'}},
        'image_model': {'id': 100},
        'title': 'shared-old',
        'prompt': 'source-old',
    }
    rows['generation_tasks'][0]['config_snapshot'] = deepcopy(snapshot)
    plan = build_plan(rows, foreign_keys)
    assert plan.target_rows['generation_tasks'][0]['config_snapshot'] == snapshot


def test_collection_snapshot_maps_platform_source_but_not_adapter_config_or_checkpoint(
    minimal_plan_input: PlanInput,
) -> None:
    rows, foreign_keys = minimal_plan_input
    opaque = {'source_id': 'source-old', 'templateId': 'template-old', 'cursor': 'external-only'}
    snapshot = {
        'source_id': 'source-old',
        'source': {'id': 'source-old', 'config': deepcopy(opaque)},
        'config': deepcopy(opaque),
        'checkpoint': deepcopy(opaque),
    }
    rows['collection_runs'][0]['config_snapshot'] = deepcopy(snapshot)
    rows['collection_runs'][0]['checkpoint'] = deepcopy(opaque)
    plan = build_plan(rows, foreign_keys)
    result = plan.target_rows['collection_runs'][0]
    expected = str(plan.mappings['data_sources']['source-old'])
    assert result['config_snapshot']['source_id'] == expected
    assert result['config_snapshot']['source']['id'] == expected
    assert result['config_snapshot']['source']['config'] == opaque
    assert result['config_snapshot']['config'] == opaque
    assert result['config_snapshot']['checkpoint'] == opaque
    assert result['checkpoint'] == opaque
    paths = {item['path'] for item in plan.rewrites if '.config_snapshot.' in item['path']}
    assert paths == {
        'collection_runs[0].config_snapshot.source_id',
        'collection_runs[0].config_snapshot.source.id',
    }
    assert rows['collection_runs'][0]['config_snapshot'] == snapshot


def test_system_schedule_and_retry_keys_follow_numeric_fk_without_changing_slot(minimal_plan_input: PlanInput) -> None:
    rows, foreign_keys = minimal_plan_input
    slot = '2026-10-25T08:03:00+08:00'
    rows['generation_tasks'][0]['request_id'] = f'schedule:schedule-old:{slot}'
    rows['collection_runs'][0].update(trigger_type='schedule', request_id=f'schedule:source-old:{slot}')
    rows['collection_runs'][1].update(trigger_type='retry', request_id='retry:run-root')
    plan = build_plan(rows, foreign_keys)
    tasks, runs = plan.target_rows['generation_tasks'], plan.target_rows['collection_runs']
    assert tasks[0]['request_id'] == f'schedule:{tasks[0]["schedule_id"]}:{slot}'
    assert runs[0]['request_id'] == f'schedule:{runs[0]["source_id"]}:{slot}'
    assert runs[1]['request_id'] == f'retry:{runs[1]["parent_id"]}'


@pytest.mark.parametrize('key', ['manual:source-old', 'custom:run-root', 'schedule:unrelated:slot', 'retry:unrelated'])
def test_manual_custom_and_nonmatching_keys_and_execution_tokens_remain_opaque(
    minimal_plan_input: PlanInput, key: str,
) -> None:
    rows, foreign_keys = minimal_plan_input
    for table in ('generation_tasks', 'collection_runs'):
        rows[table][0].update(request_id=key, execution_token='source-old')
    rows['collection_runs'][0]['trigger_type'] = 'manual'
    plan = build_plan(rows, foreign_keys)
    for table in ('generation_tasks', 'collection_runs'):
        assert plan.target_rows[table][0]['request_id'] == key
        assert plan.target_rows[table][0]['execution_token'] == 'source-old'


@pytest.mark.parametrize('changed', [False, True])
def test_real_request_fingerprint_uses_shared_helper_when_request_changes(
    minimal_plan_input: PlanInput, changed: bool,
) -> None:
    rows, foreign_keys = minimal_plan_input
    request = {'title': '保留中文与空格', 'limit': 3}
    if changed:
        request['template_id'] = 'template-old'
    digest = (sha256(json.dumps(request, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
              if changed else ids.generation_request_fingerprint(request, []))
    rows['generation_tasks'][0]['config_snapshot'] = {'request': request, 'request_fingerprint': digest}
    plan = build_plan(rows, foreign_keys)
    snapshot = plan.target_rows['generation_tasks'][0]['config_snapshot']
    expected = ids.generation_request_fingerprint(snapshot['request'], [])
    assert snapshot['request_fingerprint'] == expected
    assert (expected != digest) is changed


@pytest.mark.parametrize('field', ['materials', 'selected_item_ids'])
@pytest.mark.parametrize('scalar_type', [int, str])
def test_migrated_fingerprint_matches_raw_scalar_replay_with_frozen_typed_materials(
    numeric_plan_input: PlanInput, field: str, scalar_type: type,
) -> None:
    rows, foreign_keys = numeric_plan_input
    original = rows['generation_tasks'][0]['config_snapshot']
    # Simulate a genuine historical 64-hex fingerprint from the old queue.
    original['request_fingerprint'] = sha256(json.dumps(original['request'], sort_keys=True).encode()).hexdigest()
    plan = build_plan(rows, foreign_keys)
    task = plan.target_rows['generation_tasks'][0]
    snapshot = task['config_snapshot']
    replay = deepcopy(snapshot['request'])
    replay.pop('selected_item_ids')
    replay[field] = [scalar_type(item['id']) for item in task['materials']]
    replay['template_id'] = int(replay['template_id'])
    replay['report_id'] = int(replay['report_id'])
    replay['request_id'] = task['request_id']
    expected = ids.generation_request_fingerprint(snapshot['request'], task['materials'])
    assert snapshot['request_fingerprint'] == expected
    assert ids.generation_request_fingerprint(replay, task['materials']) == expected
    # A client explicitly changing the type must not pass idempotency comparison.
    changed = deepcopy(snapshot['request'])
    changed['selected_item_ids'][0]['type'] = 'paper'
    assert ids.generation_request_fingerprint(changed, task['materials']) != expected


def test_remapped_system_key_collision_is_rejected(minimal_plan_input: PlanInput) -> None:
    rows, foreign_keys = minimal_plan_input
    new_schedule = build_plan(rows, foreign_keys).mappings['digest_schedules']['schedule-old']
    rows['generation_tasks'][0]['request_id'] = 'schedule:schedule-old:slot'
    duplicate = deepcopy(rows['generation_tasks'][0])
    duplicate.update(id='task-second', schedule_id=None, request_id=f'schedule:{new_schedule}:slot')
    rows['generation_tasks'].append(duplicate)
    with pytest.raises(ValueError, match='idempotency keys collide'):
        build_plan(rows, foreign_keys)


def test_nonempty_schedule_time_can_be_archived_and_fingerprinted(minimal_plan_input: PlanInput) -> None:
    rows, foreign_keys = minimal_plan_input
    rows['digest_schedules'][0]['run_time'] = time(8, 5, 3, 123456)
    plan = build_plan(rows, foreign_keys)
    assert plan.target_rows['digest_schedules'][0]['run_time'] == time(8, 5, 3, 123456)
    assert json.loads(migration._json(rows['digest_schedules']))[0]['run_time'] == '08:05:03.123456'
    assert len(migration.fingerprint(rows['digest_schedules'])) == len(sha256().hexdigest())
