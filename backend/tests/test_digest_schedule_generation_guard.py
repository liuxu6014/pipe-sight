"""Schedule generation parameters cannot replace automatic evidence or model policy."""

# Shared offline fixture doubles and business examples follow research tests.
# ruff: noqa: ANN001, ANN201, ANN204, PLR2004

import importlib
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, time, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import seed

env = memory_env
db = memory_db
no_external_network = offline_network

PROTECTED_KEYS = [
    'materials',
    'selected_item_ids',
    'selectedItemIds',
    'template_id',
    'templateId',
    'report_id',
    'reportId',
    'request_id',
    'requestId',
    'report_type',
    'reportType',
    'type',
    'title',
    'period',
    'selection_strategy',
    'selectionStrategy',
    'user_id',
    'userId',
    'model_id',
    'modelId',
    'image_model_id',
    'imageModelId',
    'schedule_id',
    'scheduleId',
    'unknown_setting',
]


async def setup_template(env, db, *, model=True, image=False):
    template, material = seed(env, db, model=model, image=image)
    template.purpose = 'digest'
    template.name = '通用简报模板'
    await db.commit()
    return template, material


def schedule_payload(**changes):
    return {
        'name': 'Automatic daily',
        'template_id': '201',
        'report_type': 'daily',
        'schedule_time': '08:00',
        **changes,
    }


async def create(env, db, **changes):
    return await env.schedules.DigestScheduleService.create(
        db,
        user_id=7,
        owner_name='owner',
        payload=schedule_payload(**changes),
        template_service=env.template.PipelineTemplateService,
    )


class DispatchWindow:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    def __getattr__(self, name):
        return getattr(self.db, name)

    @asynccontextmanager
    async def begin_nested(self):
        with self.db.s.begin_nested():
            yield


async def dispatch_fixture(env, db, monkeypatch, generation_config, *, candidates=None, selection_config=None, candidate_loader=None, frequency='daily'):
    now = datetime(2026, 10, 25, tzinfo=timezone.utc)
    row = env.models.PipelineDigestSchedule(
        id=501,
        user_id=7,
        template_id=201,
        name='Daily',
        frequency=frequency,
        weekday=6 if frequency == 'weekly' else None,
        month_day=25 if frequency == 'monthly' else None,
        run_time=time(8),
        timezone='Asia/Shanghai',
        is_enabled=True,
        next_run_at=now,
        selection_config=selection_config or {'limit': 50},
        generation_config=deepcopy(generation_config),
    )
    db.add(row)
    await db.commit()
    monkeypatch.setattr(env.schedules, 'AsyncSessionLocal', lambda: DispatchWindow(db))
    monkeypatch.setattr(env.repo.ResearchDao, 'list_due_schedules', AsyncMock(return_value=[row]))
    candidate_query = AsyncMock(side_effect=candidate_loader) if candidate_loader else AsyncMock(return_value=candidates or [])
    monkeypatch.setattr(env.repo.ResearchDao, 'digest_candidates', candidate_query)
    enqueue = AsyncMock(return_value={})
    monkeypatch.setattr(env.schedules.ResearchJobService, 'queue', enqueue)
    result = await env.schedules.DigestScheduleService.dispatch_due(
        stage_labels=[],
        job_serializer=lambda *a, **k: {},
        template_service=env.template.PipelineTemplateService,
    )
    return result, row, enqueue, candidate_query, now


@pytest.mark.asyncio
@pytest.mark.parametrize('key', PROTECTED_KEYS)
async def test_create_rejects_unknown_and_protected_generation_overrides(env, db, key):
    await setup_template(env, db)
    with pytest.raises(env.exc):
        await create(env, db, generation_config={key: []})
    assert not db.s.scalars(select(env.models.PipelineDigestSchedule)).all()


@pytest.mark.asyncio
@pytest.mark.parametrize('key', ['materials', 'selectedItemIds', 'templateId', 'modelId', 'unknown_setting'])
async def test_historical_overrides_fail_dispatch_without_advancing_cursor_or_enqueue(env, db, monkeypatch, key):
    await setup_template(env, db)
    result, row, enqueue, _, before = await dispatch_fixture(env, db, monkeypatch, {key: []})
    assert result['failed'] == 1 and result['queued'] == 0
    assert env.repo.ResearchDao.aware(row.next_run_at) == before
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_generation_aliases_are_canonical_without_mutating_input(env, db):
    await setup_template(env, db, image=True)
    config = {
        'citationCheck': False,
        'diagram': False,
        'requirements': 'Keep original text',
        'outline': [{'id': 1, 'title': 'My section'}],
        'options': {'generate_images': True, 'summary_length': 'long'},
    }
    before = deepcopy(config)
    result = await create(env, db, generation_config=config)
    assert result['generationConfig']['citation_check'] is False
    assert result['generationConfig']['options'] == {'generateImages': True, 'summaryLength': 'long'}
    assert config == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'config',
    [
        {'citationCheck': True, 'citation_check': False},
        {'options': {'generateImages': True, 'generate_images': False}},
        {'options': {'materials': []}},
        {'options': {'modelId': '1'}},
        {'diagram': 'false'},
        {'options': {'generateImages': 'false'}},
        {'outline': 'not a list'},
        {'options': []},
        ['not a dict'],
    ],
)
async def test_generation_dict_validation_rejects_ambiguous_aliases_and_invalid_types(env, db, config):
    await setup_template(env, db)
    with pytest.raises(env.exc):
        await create(env, db, generation_config=config)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'issue', ['missing', 'disabled', 'capability', 'provider', 'template_disabled', 'purpose', 'image']
)
async def test_enabled_create_rejects_unusable_template_or_models(env, db, issue):
    template, _ = await setup_template(env, db, model=issue != 'missing')
    if issue in {'disabled', 'capability', 'provider'}:
        model = await env.repo.ResearchDao.get_model(db, 1)
        if issue == 'disabled':
            model.is_enabled = False
        elif issue == 'capability':
            model.capabilities = ['image_generate']
        else:
            model.provider = 'unsupported-provider'
    elif issue == 'template_disabled':
        template.is_enabled = False
    elif issue == 'purpose':
        template.purpose = 'research'
    await db.commit()
    with pytest.raises(env.exc):
        await create(env, db, generation_config={'options': {'generateImages': issue == 'image'}})
    assert not db.s.scalars(select(env.models.PipelineDigestSchedule)).all()


@pytest.mark.asyncio
@pytest.mark.parametrize('issue', ['missing', 'disabled', 'capability', 'image', 'template_disabled'])
async def test_disabled_draft_is_saved_but_cannot_enable_before_model_configuration(env, db, issue):
    template, _ = await setup_template(env, db, model=issue != 'missing')
    if issue in {'disabled', 'capability'}:
        model = await env.repo.ResearchDao.get_model(db, 1)
        if issue == 'disabled':
            model.is_enabled = False
        else:
            model.capabilities = ['image_generate']
    elif issue == 'template_disabled':
        template.is_enabled = False
    await db.commit()
    result = await create(env, db, enabled=False, generation_config={'diagram': issue == 'image'})
    assert result['enabled'] is False and result['nextRunTime'] == ''
    with pytest.raises(env.exc):
        await env.schedules.DigestScheduleService.set_enabled(db, 7, result['id'], True)
    row = await env.repo.ResearchDao.lock_digest_schedule_for_update(db, result['id'], 7)
    assert not row.is_enabled and row.next_run_at is None


@pytest.mark.asyncio
async def test_reenable_rechecks_models_even_after_previously_valid_create(env, db):
    await setup_template(env, db)
    result = await create(env, db)
    await env.schedules.DigestScheduleService.set_enabled(db, 7, result['id'], False)
    model = await env.repo.ResearchDao.get_model(db, 1)
    model.is_enabled = False
    await db.commit()
    with pytest.raises(env.exc):
        await env.schedules.DigestScheduleService.set_enabled(db, 7, result['id'], True)


@pytest.mark.asyncio
@pytest.mark.parametrize('issue', ['missing', 'disabled', 'capability', 'template_disabled', 'image'])
async def test_dispatch_rechecks_configuration_before_enqueue(env, db, monkeypatch, issue):
    template, _ = await setup_template(env, db, model=issue != 'missing')
    if issue in {'disabled', 'capability'}:
        model = await env.repo.ResearchDao.get_model(db, 1)
        if issue == 'disabled':
            model.is_enabled = False
        else:
            model.capabilities = []
    if issue == 'template_disabled':
        template.is_enabled = False
    await db.commit()
    candidates = [SimpleNamespace(id=101, title='Current candidate', content='Real body', content_zh=None)]
    result, row, enqueue, _, before = await dispatch_fixture(
        env,
        db,
        monkeypatch,
        {'diagram': issue == 'image'},
        candidates=candidates,
    )
    assert result['failed'] == 1 and result['queued'] == 0
    assert env.repo.ResearchDao.aware(row.next_run_at) == before
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('requirements', [
    'Original requirements',
    '报告周期：2020-01-01 至 2020-01-02；Original requirements',
])
async def test_dispatch_keeps_filtered_candidate_order_and_fifty_limit(env, db, monkeypatch, requirements):
    await setup_template(env, db)
    candidates = [
        SimpleNamespace(id=i, title=f'Candidate {i}', content='Real body', content_zh=None) for i in range(1, 76)
    ]
    before = deepcopy([vars(item) for item in candidates])
    selection = {'source_ids': ['601'], 'category_ids': ['801'], 'keywords': ['管网'], 'limit': 50}
    result, row, enqueue, query, _ = await dispatch_fixture(
        env,
        db,
        monkeypatch,
        {'citationCheck': False, 'requirements': requirements},
        candidates=candidates,
        selection_config=selection,
    )
    assert result['queued'] == 1 and result['failed'] == 0
    data = enqueue.await_args.kwargs['payload']
    assert data['selected_item_ids'] == [str(i) for i in range(1, 51)]
    assert 'materials' not in data and data['citation_check'] is False
    assert data['period'] == ['2026-10-24']
    assert data['requirements'] == '报告周期：2026-10-24 至 2026-10-24；Original requirements'
    assert row.generation_config['requirements'] == requirements
    assert data['selection_strategy']['candidate_count'] == 75
    assert query.await_args.args[-1] == selection
    assert [vars(item) for item in candidates] == before


@pytest.mark.asyncio
async def test_injected_fifty_one_materials_are_rejected_not_truncated(env, db):
    await setup_template(env, db)
    with pytest.raises(env.exc):
        await create(
            env, db, generation_config={'materials': [{'type': 'article', 'id': str(i)} for i in range(1, 52)]}
        )


@pytest.mark.asyncio
async def test_runtime_create_dict_aliases_are_validated_not_ignored(env, db):
    await setup_template(env, db)
    result = await env.schedules.DigestScheduleService.create(
        db,
        user_id=7,
        owner_name='owner',
        template_service=env.template.PipelineTemplateService,
        payload={
            'name': 'Alias plan',
            'templateId': '201',
            'reportType': 'daily',
            'generationConfig': {'citationCheck': False},
        },
    )
    assert result['generationConfig'] == {'citation_check': False}


@pytest.mark.asyncio
@pytest.mark.parametrize('key', ['generationConfig', 'materials', 'selectedItemIds'])
async def test_runtime_create_dict_cannot_hide_protected_payload_under_alias(env, db, key):
    await setup_template(env, db)
    data = schedule_payload()
    data[key] = {'materials': [{'type': 'file', 'id': '101'}]} if key == 'generationConfig' else ['101']
    with pytest.raises(env.exc):
        await env.schedules.DigestScheduleService.create(
            db,
            user_id=7,
            owner_name='owner',
            payload=data,
            template_service=env.template.PipelineTemplateService,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['missing', 'disabled', 'capability', 'provider'])
async def test_image_requests_require_image_capability_without_mutating_template(env, db, change):
    template, _ = await setup_template(env, db, image=change != 'missing')
    if change != 'missing':
        image = await env.repo.ResearchDao.get_model(db, 2)
        if change == 'disabled':
            image.is_enabled = False
        elif change == 'capability':
            image.capabilities = ['text_generate']
        else:
            image.provider = 'unsupported-provider'
        await db.commit()
    with pytest.raises(env.exc):
        await create(env, db, generation_config={'options': {'generate_images': True}})
    assert template.image_config == {}


@pytest.mark.asyncio
async def test_valid_disabled_draft_can_enable_and_run_now_with_models(env, db):
    await setup_template(env, db, image=True)
    result = await create(env, db, enabled=False, generation_config={'diagram': True})
    enabled = await env.schedules.DigestScheduleService.set_enabled(db, 7, result['id'], True)
    assert enabled['enabled'] and enabled['nextRunTime']
    run = await env.schedules.DigestScheduleService.run_now(db, 7, result['id'])
    assert run['enabled'] and run['nextRunTime']


@pytest.mark.asyncio
async def test_invalid_historical_generation_is_rejected_on_reenable(env, db):
    await setup_template(env, db)
    result = await create(env, db, enabled=False)
    row = await env.repo.ResearchDao.lock_digest_schedule_for_update(db, result['id'], 7)
    row.generation_config = {'selectedItemIds': ['101']}
    await db.commit()
    with pytest.raises(env.exc):
        await env.schedules.DigestScheduleService.set_enabled(db, 7, result['id'], True)
    assert not row.is_enabled and row.next_run_at is None


@pytest.mark.asyncio
async def test_manual_fifty_selections_across_pages_are_not_limited_by_automatic_item_count(env, db, monkeypatch):
    evidence = importlib.import_module('app.research.services.evidence')
    articles = {
        i: SimpleNamespace(
            id=i,
            title='Same visible title',
            content='Real body',
            content_zh=None,
            source_id=601,
            url=f'https://offline.invalid/{i}',
            published_at=None,
        )
        for i in range(1, 51)
    }

    async def load(_db, kind, identity) -> SimpleNamespace | None:
        return articles.get(identity) if kind == 'article' else None

    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', load)
    selected = [{'type': 'article', 'id': str(i)} for i in range(1, 51)]
    frozen = await evidence.ResearchEvidenceService.resolve(db, 7, selected, {'options': {'itemCount': 1}})
    assert [item['id'] for item in frozen] == [str(i) for i in range(1, 51)]


@pytest.mark.asyncio
async def test_dispatch_validates_models_even_with_no_current_candidates(env, db, monkeypatch):
    await setup_template(env, db, model=False)
    result, row, enqueue, candidates, before = await dispatch_fixture(env, db, monkeypatch, {})
    assert result['failed'] == 1 and result['no_data'] == 0
    assert env.repo.ResearchDao.aware(row.next_run_at) == before
    enqueue.assert_not_awaited()
    candidates.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_now_revalidates_models_before_cursor_change(env, db):
    await setup_template(env, db)
    result = await create(env, db)
    row = await env.repo.ResearchDao.lock_digest_schedule_for_update(db, result['id'], 7)
    previous = row.next_run_at
    model = await env.repo.ResearchDao.get_model(db, 1)
    model.is_enabled = False
    await db.commit()
    with pytest.raises(env.exc):
        await env.schedules.DigestScheduleService.run_now(db, 7, result['id'])
    assert row.next_run_at == previous
