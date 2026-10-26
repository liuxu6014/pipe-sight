"""Replay the original frontend request after ID migration, not just its snapshot.

Uses real in-memory queue persistence and mocked existing migrated jobs; no PG,
network, model calls, production edits, or source-body reload on replay.
"""

# Fixture doubles and literal examples follow the existing research test suite.
# ruff: noqa: ANN001, ANN201

import importlib
import json
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import payload, queue, seed

env = memory_env
db = memory_db
no_external_network = offline_network


def fingerprint(request, materials):
    return importlib.import_module('app.business_ids').generation_request_fingerprint(request, materials)


@pytest.fixture
def migrated(env):
    migration = importlib.import_module('app.numeric_id_migration')
    rows = {name: [] for name in migration.BUSINESS_ID_TABLES}
    original = {
        'title': 'Original frontend request',
        'report_type': 'research',
        'template_id': 'template-old',
        'selected_item_ids': ['shared-old'],
        'requirements': 'Preserve requested content',
        'options': {},
    }
    legacy_hash = sha256(json.dumps(original, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    stored_request = deepcopy(original)
    stored_request['selected_item_ids'] = [{'type': 'file', 'id': 'shared-old'}]
    rows['templates'] = [{'id': 'template-old'}]
    rows['knowledge_files'] = [{'id': 'shared-old', 'user_id': 7}]
    # Legacy cross-table collisions must be resolved by frozen evidence type.
    rows['papers'] = [{'id': 'shared-old'}]
    rows['reports'] = [{'id': 'report-old', 'template_id': 'template-old', 'user_id': 7}]
    rows['generation_tasks'] = [
        {
            'id': 'task-old',
            'report_id': 'report-old',
            'schedule_id': None,
            'request_id': 'manual:client-opaque-token',
            'materials': [
                {
                    'type': 'file',
                    'id': 'shared-old',
                    'title': 'Frozen title',
                    'content': 'Frozen authorized body',
                    'source': {'filename': 'original.txt'},
                }
            ],
            'config_snapshot': {'request': stored_request, 'request_fingerprint': legacy_hash},
        }
    ]
    before = deepcopy(rows)
    foreign_keys = [
        {'table': 'reports', 'columns': ['template_id'], 'target': 'templates', 'target_columns': ['id']},
        {'table': 'generation_tasks', 'columns': ['report_id'], 'target': 'reports', 'target_columns': ['id']},
    ]
    plan = migration.build_plan(rows, foreign_keys)
    current = deepcopy(original)
    current['template_id'] = str(plan.mappings['templates']['template-old'])
    current['selected_item_ids'] = [str(plan.mappings['knowledge_files']['shared-old'])]
    task = plan.target_rows['generation_tasks'][0]
    assert rows == before
    return SimpleNamespace(original=original, legacy_hash=legacy_hash, task=task, current=current, plan=plan)


def test_original_scalar_request_replays_after_typed_snapshot_and_build_plan(migrated):
    task = migrated.task
    assert (
        migrated.legacy_hash
        == sha256(json.dumps(migrated.original, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    )
    assert isinstance(migrated.current['selected_item_ids'][0], str)
    assert isinstance(task['config_snapshot']['request']['selected_item_ids'][0], dict)
    # This compares to the actual frontend scalar replay, not snapshot-to-snapshot.
    assert fingerprint(migrated.current, task['materials']) == task['config_snapshot']['request_fingerprint']
    assert task['materials'][0]['content'] == 'Frozen authorized body'
    assert task['request_id'] == 'manual:client-opaque-token'


@pytest.mark.parametrize('shape', ['scalar', 'typed', 'materials', 'snapshot'])
def test_all_supported_replay_shapes_share_one_hash(migrated, shape):
    data = deepcopy(migrated.current)
    reference = {'type': 'file', 'id': data['selected_item_ids'][0]}
    if shape == 'typed':
        data['selected_item_ids'] = [reference]
    elif shape == 'materials':
        data.pop('selected_item_ids')
        data['materials'] = [reference]
    elif shape == 'snapshot':
        data = deepcopy(migrated.task['config_snapshot']['request'])
    before = deepcopy(data)
    assert fingerprint(data, migrated.task['materials']) == migrated.task['config_snapshot']['request_fingerprint']
    assert data == before


@pytest.mark.parametrize('change', ['type', 'selection', 'content', 'request'])
def test_changed_type_selection_content_or_request_does_not_replay(migrated, change):
    data = deepcopy(migrated.current)
    if change == 'type':
        data['selected_item_ids'] = [{'type': 'paper', 'id': data['selected_item_ids'][0]}]
    elif change == 'selection':
        data['selected_item_ids'] = [str(migrated.plan.mappings['papers']['shared-old'])]
    elif change == 'content':
        data['requirements'] = 'Changed requested content'
    else:
        data['title'] = 'A different request'
    assert fingerprint(data, migrated.task['materials']) != migrated.task['config_snapshot']['request_fingerprint']


def test_source_body_and_metadata_are_not_reloaded_to_compute_replay(migrated):
    changed_source = deepcopy(migrated.task['materials'])
    changed_source[0].update(content='Source body was later edited', title='Later title')
    changed_source[0]['source'] = {'filename': 'renamed.txt'}
    assert fingerprint(migrated.current, changed_source) == migrated.task['config_snapshot']['request_fingerprint']


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', [False, True])
async def test_migrated_existing_queue_uses_frozen_evidence_without_loading_sources(
    env, migrated, monkeypatch, changed
):
    jobs = importlib.import_module('app.research.services.jobs')
    existing = SimpleNamespace(**deepcopy(migrated.task))
    report = SimpleNamespace(id=existing.report_id, user_id=7)
    monkeypatch.setattr(jobs.ResearchDao, 'get_research_job_by_request_id', AsyncMock(return_value=existing))
    owned_report = AsyncMock(return_value=report)
    monkeypatch.setattr(jobs.ResearchDao, 'get_report', owned_report)
    resolve = AsyncMock(side_effect=AssertionError('Existing replay must not reload source bodies'))
    monkeypatch.setattr(jobs.ResearchEvidenceService, 'resolve', resolve)
    data = deepcopy(migrated.current)
    data['request_id'] = 'client-opaque-token'
    if changed:
        data['selected_item_ids'] = [{'type': 'paper', 'id': data['selected_item_ids'][0]}]
    templates = SimpleNamespace(get_published=AsyncMock(side_effect=AssertionError('No template reload on replay')))
    call = jobs.ResearchJobService.queue(
        SimpleNamespace(),
        user_id=7,
        owner_name='owner',
        payload=data,
        stage_labels=[],
        job_serializer=lambda job, report: {'jobId': str(job.id), 'reportId': str(report.id)},
        template_service=templates,
    )
    if changed:
        with pytest.raises(env.exc) as error:
            await call
        assert '幂等键' in error.value.message
    else:
        result = await call
        assert result['reused'] is True and result['jobId'] == str(existing.id)
        owned_report.assert_awaited_once_with(SimpleNamespace(), existing.report_id, 7)
    resolve.assert_not_awaited()
    templates.get_published.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('shape', ['scalar', 'typed', 'materials'])
async def test_real_memory_queue_first_submit_then_existing_replay_after_source_deleted(env, db, monkeypatch, shape):
    _, material = seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    first_request = payload(request_id='replay-key')
    first = await queue(env, db, deepcopy(first_request))
    assert first['reused'] is False
    job = await env.repo.ResearchDao.get_research_job(db, first['jobId'], 7)
    assert isinstance(job.config_snapshot['request']['selected_item_ids'][0], dict)
    assert fingerprint(first_request, job.materials) == job.config_snapshot['request_fingerprint']
    frozen = deepcopy(job.materials)
    await db.delete(material)
    await db.commit()
    jobs = importlib.import_module('app.research.services.jobs')
    resolve = AsyncMock(side_effect=AssertionError('Deleted source must not be re-resolved'))
    monkeypatch.setattr(jobs.ResearchEvidenceService, 'resolve', resolve)
    replay = deepcopy(first_request)
    if shape == 'typed':
        replay['selected_item_ids'] = [{'type': 'file', 'id': '101'}]
    elif shape == 'materials':
        replay['selected_item_ids'] = []
        replay['materials'] = [{'type': 'file', 'id': '101'}]
    second = await queue(env, db, replay)
    assert second['reused'] is True and second['jobId'] == first['jobId']
    assert job.materials == frozen
    assert len(db.s.scalars(select(env.models.PipelineResearchJob)).all()) == 1
    resolve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['type', 'content', 'request', 'owner'])
async def test_real_memory_existing_queue_rejects_mutation_and_wrong_owner(env, db, monkeypatch, change):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    data = payload(request_id='conflict-key')
    first = await queue(env, db, deepcopy(data))
    if change == 'type':
        data['selected_item_ids'] = [{'type': 'paper', 'id': '101'}]
    elif change == 'content':
        data['requirements'] = 'Different requested content'
    elif change == 'request':
        data['title'] = 'Different requested report'
    with pytest.raises(env.exc) as error:
        await queue(env, db, data, user_id=8 if change == 'owner' else 7)
    assert '幂等键' in error.value.message
    assert len(db.s.scalars(select(env.models.PipelineResearchJob)).all()) == 1
    assert str(db.s.scalars(select(env.models.PipelineResearchJob)).one().id) == first['jobId']
