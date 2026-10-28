"""G01/G02/G03/G04/G07/G11：纯内存对象与 AsyncMock，无数据库/模型/调度写入。"""

# 与共享离线测试夹具一致，使用动态服务对象。
# ruff: noqa: ANN001, ANN201, N814

import importlib
import json
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, time, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from test_research_simplified_20261025 import env as offline_env
from test_research_simplified_20261025 import no_external_network as offline_network

env = offline_env
no_external_network = offline_network


def template(**updates):
    return NS(id=201, name='日报', purpose='digest', description='', prompt='模板要求',
              model_id=1, image_model_id=None, sections=[], image_config={}, is_enabled=True,
              updated_at=None, **updates)


@pytest.mark.parametrize(('name', 'purpose', 'expected'), [
    ('日报', 'digest', 'daily'), ('周报', 'digest', 'weekly'), ('月报', 'digest', 'monthly'),
    ('科技情报日报', 'digest', 'daily'), ('管网科技情报月报', 'digest', 'monthly'),
    ('通用简报', 'digest', 'all'), ('未知模板', 'digest', None),
    ('日报周报月报', 'digest', None), ('日报', 'research', None),
])
def test_template_cadence_is_explicit_and_keeps_legacy_fields(env, name, purpose, expected):
    row = template()
    row.name, row.purpose = name, purpose
    result = env.template.PipelineTemplateService._dict(row)
    assert result.get('digestCadence', 'missing') == expected
    assert result['purpose'] == result['reportType'] == purpose


def queue_mocks(env, monkeypatch, row):
    jobs = importlib.import_module('app.research.services.jobs')
    model = NS(id=1, provider='compatible', code='offline', base_url='https://offline.invalid', parameters={})
    service = NS(get_published=AsyncMock(return_value=row), validate_models=AsyncMock(return_value=model))
    monkeypatch.setattr(env.repo.ResearchDao, 'get_research_job_by_request_id', AsyncMock(return_value=None))
    monkeypatch.setattr(env.repo.ResearchDao, 'add_report', AsyncMock(side_effect=lambda db, report: setattr(report, 'id', 301)))
    add_job = AsyncMock()
    monkeypatch.setattr(env.repo.ResearchDao, 'add_research_job', add_job)
    monkeypatch.setattr(jobs.ResearchEvidenceService, 'resolve', AsyncMock(return_value=[
        {'type': 'file', 'id': '101', 'title': '证据', 'content': '原文', 'source': {}}
    ]))
    return jobs, service, add_job


@pytest.mark.asyncio
@pytest.mark.parametrize('name', ['月报', '未知模板'])
async def test_manual_submission_rejects_wrong_or_unknown_cadence_before_enqueue(env, monkeypatch, name):
    row = template()
    row.name = name
    jobs, service, enqueue = queue_mocks(env, monkeypatch, row)
    with pytest.raises(env.exc) as caught:
        await jobs.ResearchJobService.queue(
            AsyncMock(), user_id=7, owner_name='', payload={
                'title': '日报任务', 'report_type': 'daily', 'template_id': '201', 'selected_item_ids': ['101']
            }, stage_labels=[], job_serializer=lambda *a, **k: {}, template_service=service,
        )
    assert '周期' in caught.value.message
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('choice', [{'diagram': False}, {'options': {'generateImages': False}},
                                  {'diagram': False, 'options': {'generateImages': True}}])
async def test_explicit_image_off_overrides_template_before_model_validation(env, monkeypatch, choice):
    row = template()
    row.image_config = {'enabled': True, 'count': 2}
    jobs, service, enqueue = queue_mocks(env, monkeypatch, row)
    original = deepcopy(row.image_config)
    await jobs.ResearchJobService.queue(
        AsyncMock(), user_id=7, owner_name='', payload={
            'title': '日报任务', 'report_type': 'daily', 'template_id': '201', 'selected_item_ids': ['101'], **choice
        }, stage_labels=[], job_serializer=lambda *a, **k: {}, template_service=service,
    )
    assert all(call.args[3]['enabled'] is False for call in service.validate_models.await_args_list)
    snapshot = enqueue.await_args.args[1].config_snapshot
    assert snapshot['template']['image_config']['enabled'] is False
    assert 'image_model' not in snapshot and row.image_config == original


@pytest.mark.asyncio
async def test_model_instructions_include_business_boundaries_and_output_options(env, monkeypatch):
    request = {'direction': '漏损研究', 'project': '示范工程', 'scenario': '地下管道',
               'period': ['2026-10-01', '2026-10-31'], 'keywords': ['声学'], 'requirements': '用户要求',
               'options': {'language': 'zh', 'length': 'long', 'summaryLength': 'short',
                           'hotAnalysis': False, 'duplicateMerge': True, 'itemCount': 3}}
    snapshot = {'title': '月报', 'type': 'monthly', 'request': request,
                'template': {'prompt': '模板', 'sections': []}, 'model': {}}
    before = deepcopy(snapshot)
    call = AsyncMock(return_value='离线正文')
    monkeypatch.setattr(env.gateway.ModelGateway, 'call', call)
    await env.gateway.ResearchModelGenerationService.generate_content(None, snapshot, [], task_id=1)
    instructions = json.loads(call.await_args.kwargs['prompt'].split('\n')[1])
    for field in ('direction', 'project', 'scenario', 'period', 'keywords'):
        assert instructions.get(field) == request[field]
    assert instructions.get('reportType') == 'monthly'
    assert instructions.get('options') == request['options']
    assert snapshot == before


@asynccontextmanager
async def mock_session(db):
    yield db


@pytest.mark.asyncio
async def test_schedule_rebuilds_current_period_without_mutating_saved_preferences(env, monkeypatch):
    row = NS(id=501, user_id=7, template_id=201, name='日报', frequency='daily', run_time=time(8),
             timezone='Asia/Shanghai', next_run_at=datetime(2026, 10, 26, tzinfo=timezone.utc),
             selection_config={'keywords': ['漏损'], 'limit': 5},
             generation_config={'requirements': '报告周期：2020-01-01；来源范围：新闻网站；自定义关注管网',
                                'direction': '监测', 'options': {'sources': ['新闻网站']}})
    before = deepcopy(row.generation_config)
    db = AsyncMock()
    db.begin_nested = lambda: mock_session(db)
    monkeypatch.setattr(env.schedules, 'AsyncSessionLocal', lambda: mock_session(db))
    monkeypatch.setattr(env.repo.ResearchDao, 'list_due_schedules', AsyncMock(return_value=[row]))
    monkeypatch.setattr(env.repo.ResearchDao, 'digest_candidates', AsyncMock(return_value=[
        NS(id=101, title='资料', content='原文', content_zh=None)
    ]))
    enqueue = AsyncMock()
    monkeypatch.setattr(env.schedules.ResearchJobService, 'queue', enqueue)
    service = NS(get_published=AsyncMock(return_value=template()), validate_models=AsyncMock())
    result = await env.schedules.DigestScheduleService.dispatch_due(
        stage_labels=[], job_serializer=lambda *a, **k: {}, template_service=service,
    )
    assert result['queued'] == 1
    data = enqueue.await_args.kwargs['payload']
    assert '2020-01-01' not in data['requirements']
    assert data['period'][0] in data['requirements'] and data['period'][-1] in data['requirements']
    assert '来源范围：新闻网站；自定义关注管网' in data['requirements']
    assert data['keywords'] == ['漏损']
    assert row.generation_config == before


@pytest.mark.asyncio
async def test_schedule_rejects_mismatched_cadence_and_honors_image_off(env):
    row = template()
    row.image_config = {'enabled': True}
    service = NS(get_published=AsyncMock(return_value=row), validate_models=AsyncMock())
    validate = env.schedules.DigestScheduleService._validate_enabled_template
    await validate(None, 201, {'diagram': False}, service, frequency='daily')
    assert service.validate_models.await_args.args[3]['enabled'] is False
    with pytest.raises(env.exc) as caught:
        await validate(None, 201, {}, service, frequency='monthly')
    assert '周期' in caught.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize('requested', [True, False])
async def test_generated_version_records_normalization_separately_from_unrun_checks(env, monkeypatch, requested):
    execution = importlib.import_module('app.research.services.execution')
    snapshot = {'request': {'citation_check': requested}, 'template': {'id': '201'}, 'report_start_version': 1}
    job = NS(execution_token='token', config_snapshot=snapshot, materials=[], report_id=301)
    report = NS(id=301, version=1, title='报告', content='', template_id=201)
    db = AsyncMock()
    monkeypatch.setattr(execution, 'AsyncSessionLocal', lambda: mock_session(db))
    for name, value in [('claim_research_job', job), ('lock_running_research_job', job),
                        ('get_report', report), ('get_report_version', None)]:
        monkeypatch.setattr(env.repo.ResearchDao, name, AsyncMock(return_value=value))
    save = AsyncMock()
    monkeypatch.setattr(env.repo.ResearchDao, 'add_report_version', save)
    monkeypatch.setattr(execution.ResearchModelGenerationService, 'generate_content', AsyncMock(return_value='正文'))
    exports = importlib.import_module('app.research.services.exports')
    monkeypatch.setattr(exports.ResearchReportExportService, 'queue_images', AsyncMock())
    await execution.ResearchExecutionService.process(job_id=401, user_id=7)
    assert job.status == 'completed'
    version = save.await_args.args[1]
    checks = version.model_snapshot.get('checks')
    assert checks is not None
    assert checks['citation'] == {'requested': requested, 'status': 'not_run',
                                  'reason': 'normalization_only', 'normalization': 'completed', 'version': 2}
    assert checks['quality'] == {'status': 'not_run', 'version': 2}
    assert job.config_snapshot == version.model_snapshot
    assert 'checks' not in snapshot


@pytest.mark.parametrize(('choice', 'expected'), [
    ({}, True), ({'diagram': True}, True), ({'options': {'generateImages': False}}, False),
    ({'diagram': True, 'options': {'generateImages': False}}, True),
])
def test_image_selection_presence_and_precedence(env, choice, expected):
    original = {'enabled': True, 'count': 2}
    result = env.template.PipelineTemplateService.effective_image_config(original, choice)
    assert result['enabled'] is expected and original == {'enabled': True, 'count': 2}


@pytest.mark.parametrize('original', ['', '重点关注漏损', '历史案例发生于2020-01-01'])
def test_schedule_requirements_always_include_execution_period_and_keep_free_text(env, original):
    result = env.schedules.DigestScheduleService._requirements_for_period(
        {'requirements': original}, ['2026-10-01', '2026-10-31']
    )
    assert result.startswith('报告周期：2026-10-01 至 2026-10-31')
    assert original in result


@pytest.mark.asyncio
@pytest.mark.parametrize('explicit', [False, True])
async def test_pydantic_default_is_not_an_explicit_image_choice(env, monkeypatch, explicit):
    row = template()
    row.image_model_id = 2
    jobs, service, enqueue = queue_mocks(env, monkeypatch, row)
    image = NS(id=2, provider='compatible', code='image', base_url='https://offline.invalid', parameters={})
    monkeypatch.setattr(env.repo.ResearchDao, 'get_model', AsyncMock(return_value=image))
    schema = importlib.import_module('app.intelligence.schemas.pipeline')
    data = {'title': '日报', 'reportType': 'daily', 'templateId': '201', 'selectedItemIds': ['101'],
            'options': {'generateImages': True}}
    if explicit:
        data['diagram'] = False
    await jobs.ResearchJobService.queue(
        AsyncMock(), user_id=7, owner_name='', payload=schema.PipelineResearchJobCreateModel(**data),
        stage_labels=[], job_serializer=lambda *a, **k: {}, template_service=service,
    )
    snapshot = enqueue.await_args.args[1].config_snapshot
    assert snapshot['template']['image_config']['enabled'] is (not explicit)
    assert ('image_model' in snapshot) is (not explicit)


@pytest.mark.asyncio
@pytest.mark.parametrize(('initial_choice', 'legacy_snapshot'), [(None, False), (False, False), (None, True)])
async def test_image_choice_presence_is_part_of_idempotency_without_breaking_replay(
    env, monkeypatch, initial_choice, legacy_snapshot
):
    row = template()
    row.image_config = {'enabled': True}
    row.image_model_id = 2
    jobs, service, enqueue = queue_mocks(env, monkeypatch, row)
    image = NS(id=2, provider='compatible', code='image', base_url='https://offline.invalid', parameters={})
    monkeypatch.setattr(env.repo.ResearchDao, 'get_model', AsyncMock(return_value=image))
    monkeypatch.setattr(env.repo.ResearchDao, 'get_report', AsyncMock(return_value=NS(id=301)))
    schema = importlib.import_module('app.intelligence.schemas.pipeline')
    data = {'title': '日报', 'reportType': 'daily', 'templateId': '201', 'selectedItemIds': ['101'],
            'requestId': 'image-presence'}
    if initial_choice is not None:
        data['diagram'] = initial_choice

    async def submit(value) -> dict:
        return await jobs.ResearchJobService.queue(
            AsyncMock(), user_id=7, owner_name='', payload=value,
            stage_labels=[], job_serializer=lambda *a, **k: {'jobId': '401'}, template_service=service,
        )

    original = schema.PipelineResearchJobCreateModel(**data)
    assert (await submit(original))['reused'] is False
    stored = enqueue.await_args.args[1]
    assert stored.config_snapshot['template']['image_config']['enabled'] is (initial_choice is None)
    if legacy_snapshot:
        # 旧任务曾把省略补成 false，但实际冻结的图片配置仍为开启。
        stored.config_snapshot['request']['diagram'] = False
        ids = importlib.import_module('app.business_ids')
        stored.config_snapshot['request_fingerprint'] = ids.generation_request_fingerprint(
            stored.config_snapshot['request'], stored.materials
        )
    monkeypatch.setattr(env.repo.ResearchDao, 'get_research_job_by_request_id', AsyncMock(return_value=stored))
    assert (await submit(schema.PipelineResearchJobCreateModel(**data)))['reused'] is True
    # 重放已冻结的请求也必须稳定，且不重读模板或资料。
    snapshot_request = {**deepcopy(stored.config_snapshot['request']), 'request_id': 'image-presence'}
    if not legacy_snapshot:
        assert (await submit(snapshot_request))['reused'] is True
    service.get_published.assert_awaited_once()
    changed = dict(data)
    if initial_choice is None:
        changed['diagram'] = False
    else:
        changed.pop('diagram')
    with pytest.raises(env.exc) as caught:
        await submit(schema.PipelineResearchJobCreateModel(**changed))
    assert '幂等键' in caught.value.message
    enqueue.assert_awaited_once()


def test_fingerprint_preserves_pydantic_image_choice_presence(env):
    schema = importlib.import_module('app.intelligence.schemas.pipeline')
    ids = importlib.import_module('app.business_ids')
    data = {'title': '日报', 'reportType': 'daily', 'templateId': '201', 'selectedItemIds': ['101']}
    omitted = schema.PipelineResearchJobCreateModel(**data)
    explicit = schema.PipelineResearchJobCreateModel(**data, diagram=False)
    materials = [{'type': 'file', 'id': '101'}]
    omitted_hash = ids.generation_request_fingerprint(omitted, materials)
    explicit_hash = ids.generation_request_fingerprint(explicit, materials)
    assert omitted_hash != explicit_hash
    dumped = omitted.model_dump(by_alias=False)
    dumped.pop('diagram')
    assert omitted_hash == ids.generation_request_fingerprint(dumped, materials)
    assert explicit_hash == ids.generation_request_fingerprint(explicit.model_dump(by_alias=False), materials)


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['create', 'set_enabled', 'run_now'])
async def test_plan_lifecycle_rejects_unknown_cadence_without_commit(env, monkeypatch, action):
    row = template()
    row.name = '未知模板'
    plan = NS(template_id=201, frequency='daily', generation_config={}, is_enabled=True, next_run_at=None)
    service = env.template.PipelineTemplateService
    monkeypatch.setattr(service, 'get_published', AsyncMock(return_value=row))
    monkeypatch.setattr(service, 'validate_models', AsyncMock())
    monkeypatch.setattr(env.repo.ResearchDao, 'lock_digest_schedule_for_update', AsyncMock(return_value=plan))
    db = AsyncMock()
    schedules = env.schedules.DigestScheduleService
    with pytest.raises(env.exc) as caught:
        if action == 'create':
            await schedules.create(db, user_id=7, owner_name='', payload={
                'name': '日报计划', 'template_id': '201', 'report_type': 'daily'
            }, template_service=service)
        elif action == 'set_enabled':
            await schedules.set_enabled(db, 7, 501, True)
        else:
            await schedules.run_now(db, 7, 501)
    assert '周期' in caught.value.message
    assert plan.next_run_at is None
    db.commit.assert_not_awaited()
