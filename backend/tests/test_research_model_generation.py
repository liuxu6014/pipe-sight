"""规范生成任务与网关契约；无审核/发布或模拟 fallback。"""

import importlib
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_research_simplified_20261025 import AsyncMemory, payload, queue, raises, seed
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_no_external_network


def execution_context(env, db, monkeypatch):
    execution = importlib.import_module('app.research.services.execution')

    def factory():
        return AsyncMemory(Session(db.s.bind, expire_on_commit=False))

    monkeypatch.setattr(execution, 'AsyncSessionLocal', factory)
    return execution, factory


env = refactor_env
db = refactor_db
no_external_network = refactor_no_external_network


@pytest.mark.asyncio
@pytest.mark.parametrize('raw', ['## 分析\n\n无法对应的结论[99]。', '## 分析\n\n没有引用的事实正文。'])
async def test_invalid_manuscript_fails_without_overwriting_report(env, db, monkeypatch, raw):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    execution, _ = execution_context(env, db, monkeypatch)
    monkeypatch.setattr(execution.ResearchModelGenerationService, 'generate_content', AsyncMock(return_value=raw))
    await execution.ResearchExecutionService.process(job_id=result['jobId'], user_id=7)
    db.s.expire_all()
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    assert job.status == 'failed' and '文稿检查未通过' in job.error
    assert job.result_content == raw
    assert report.content == '' and report.version == 1


@pytest.mark.asyncio
async def test_task_preserves_actionable_model_output_limit_error(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    execution, _ = execution_context(env, db, monkeypatch)
    error = execution.ModelOutputLimitError(message='模型已达到输出上限，请缩短大纲')
    monkeypatch.setattr(execution.ResearchModelGenerationService, 'generate_content', AsyncMock(side_effect=error))
    await execution.ResearchExecutionService.process(job_id=result['jobId'], user_id=7)
    db.s.expire_all()
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    assert job.status == 'failed' and job.error == error.message


@pytest.mark.asyncio
async def test_duplicate_dispatch_does_not_invoke_model_without_claim(env, db, monkeypatch):
    execution, _ = execution_context(env, db, monkeypatch)
    monkeypatch.setattr(env.repo.ResearchDao, 'claim_research_job', AsyncMock(return_value=None))
    generate = AsyncMock(side_effect=AssertionError('unclaimed job must not call provider'))
    monkeypatch.setattr(execution.ResearchModelGenerationService, 'generate_content', generate)
    await execution.ResearchExecutionService.process(job_id=999999, user_id=7)
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_lost_execution_token_prevents_result_write(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    execution, factory = execution_context(env, db, monkeypatch)

    async def cancel_during_generation(model_db, *args, **kwargs):
        async with factory() as cancel_db:
            await env.app.ResearchApplicationService.cancel_job(cancel_db, 7, result['jobId'])
        return '已失效的离线结果'

    monkeypatch.setattr(execution.ResearchModelGenerationService, 'generate_content', cancel_during_generation)
    await execution.ResearchExecutionService.process(job_id=result['jobId'], user_id=7)
    db.s.expire_all()
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    assert job.status == 'cancelled' and job.result_content is None and report.content == ''


@pytest.mark.asyncio
async def test_heartbeat_uses_execution_token_and_stops_when_fenced(env, db, monkeypatch):
    execution, _ = execution_context(env, db, monkeypatch)
    touch = AsyncMock(return_value=False)
    monkeypatch.setattr(execution, 'HEARTBEAT_INTERVAL_SECONDS', 0)
    monkeypatch.setattr(env.repo.ResearchDao, 'touch_research_job', touch)
    await execution.ResearchExecutionService._heartbeat('job', 7, 'unique-token')
    assert touch.await_count == 1 and touch.await_args.kwargs['execution_token'] == 'unique-token'


@pytest.mark.asyncio
async def test_model_error_is_failed_and_never_becomes_deterministic_success(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    execution, _ = execution_context(env, db, monkeypatch)
    monkeypatch.setattr(
        execution.ResearchModelGenerationService,
        'generate_content',
        AsyncMock(side_effect=env.exc(message='模型不可用')),
    )
    await execution.ResearchExecutionService.process(job_id=result['jobId'], user_id=7)
    db.s.expire_all()
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    assert job.status == 'failed' and job.result_content is None and job.error
    assert (await env.repo.ResearchDao.get_report(db, result['reportId'], 7)).content == ''


@pytest.mark.asyncio
async def test_missing_model_blocks_submission(env, db):
    seed(env, db, model=False)
    with raises(env, 'text_generate'):
        await queue(env, db)


@pytest.mark.asyncio
async def test_new_generation_stores_canonical_citations_and_keeps_raw_provider_output(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    execution, _ = execution_context(env, db, monkeypatch)
    raw = ('## 研究内容\n\n[file:101]资料指出检测可行[file:101]（用户资料，2026-10-25），仍需验证。'
           '另一项结论[file:101]。\n\n## 参考资料\n\n[file:101] 本地资料；2026-10-25')
    monkeypatch.setattr(execution.ResearchModelGenerationService, 'generate_content', AsyncMock(return_value=raw))
    await execution.ResearchExecutionService.process(job_id=result['jobId'], user_id=7)
    db.s.expire_all()
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    version = await env.repo.ResearchDao.get_report_version(db, report.id, report.version)
    assert job.status == 'completed' and job.result_content == raw
    expected = '资料指出检测可行，仍需验证[1]。另一项结论[1]。'
    assert expected in report.content and expected == version.sections[0]['content']
    assert version.content == report.content and version.citations[0]['sourceId'] == '101'
    assert '[1] 资料；用户资料' in report.content
    assert '本地资料；2026-10-25' not in report.content  # Not present in the frozen source metadata.
    display = env.app.ResearchApplicationService.report_dict(report)
    assert display['content'] == report.content
    exported = env.app.ResearchReportService.export_snapshot(report, version)
    assert exported['content'] == report.content
    task = env.app.ResearchApplicationService.job_dict(job, report=report)
    assert task['resultContent'] == report.content and task['applyConflict'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('capability,model_id', [('text_generate', 1), ('image_generate', 2)])
@pytest.mark.parametrize('state', ['missing', 'disabled', 'wrong_capability', 'unsupported_provider'])
async def test_retry_rejects_unavailable_snapshot_model_without_changing_failed_task(
    env, db, monkeypatch, capability, model_id, state
):
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    template, _ = seed(env, db, image=True)
    template.image_config = {'enabled': True}
    await db.commit()
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    job.status, job.error, job.result_content = 'failed', '原失败原因', '保留的结果'
    await db.commit()
    model = await db.get(env.ai.AiModels, model_id)
    if state == 'missing':
        original = env.repo.ResearchDao.get_model

        async def lookup(session, item_id):
            return None if int(item_id) == model_id else await original(session, item_id)

        monkeypatch.setattr(env.repo.ResearchDao, 'get_model', lookup)
    elif state == 'disabled':
        model.is_enabled = False
    elif state == 'wrong_capability':
        model.capabilities = ['image_input']
    else:
        model.provider = 'anthropic'
    await db.commit()
    with raises(env, '协议' if state == 'unsupported_provider' else capability):
        await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=job.id)
    await db.commit()
    db.s.expire_all()
    original_job = await env.repo.ResearchDao.get_research_job(db, job.id, 7)
    assert original_job.status == 'failed' and original_job.error == '原失败原因'
    assert original_job.result_content == '保留的结果'
    assert len(db.s.scalars(select(env.models.PipelineResearchJob)).all()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('image_enabled', [False, True])
async def test_retry_with_enabled_snapshot_models_creates_new_attempt(env, db, monkeypatch, image_enabled):
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    template, _ = seed(env, db, image=image_enabled)
    template.image_config = {'enabled': image_enabled}
    await db.commit()
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    job.status, job.error = 'failed', '原失败原因'
    # 模板后来取消模型绑定，也不能替换旧任务已冻结的模型选择。
    template.model_id = template.image_model_id = None
    template.image_config = {}
    await db.commit()
    retried = await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=job.id)
    assert retried['jobId'] != str(job.id) and retried['status'] == 'queued'
    assert job.status == 'failed' and job.error == '原失败原因'


@pytest.mark.asyncio
async def test_cancel_never_changes_completed_task(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    job.status = 'completed'
    await db.commit()
    with raises(env, '已结束'):
        await env.app.ResearchApplicationService.cancel_job(db, 7, job.id)
    assert job.status == 'completed'


@pytest.mark.asyncio
async def test_gateway_rejects_native_noncompatible_provider_before_network(env, db):
    seed(env, db)
    model = await db.get(env.ai.AiModels, 1)
    model.provider = 'anthropic'
    await db.commit()
    with raises(env, '原生协议'):
        await env.gateway.ModelGateway.call(
            db,
            {'id': 1, 'provider': 'anthropic', 'code': 'text', 'base_url': model.base_url},
            capability='text_generate',
            prompt='x',
        )


@pytest.mark.asyncio
async def test_truncated_provider_output_is_not_accepted_as_a_deliverable(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    real_client = httpx.AsyncClient
    monkeypatch.setenv('OFFLINE_MODEL_KEY', 'offline-placeholder')
    monkeypatch.setattr(env.gateway.httpx, 'AsyncClient', lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            'choices': [{'finish_reason': 'length', 'message': {'content': '未写完的正文'}}],
            'usage': {'completion_tokens': 100},
        })), **kwargs))
    with raises(env, '输出上限'):
        await env.gateway.ResearchModelGenerationService.generate_content(db, job.config_snapshot, job.materials, task_id=job.id)


@pytest.mark.asyncio
async def test_gateway_uses_frozen_template_prompt_and_returns_provider_content(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    model = await db.get(env.ai.AiModels, 1)
    snapshot = job.config_snapshot
    real_client = httpx.AsyncClient
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={'choices': [{'message': {'content': '只来自离线供应商的正文'}}]})

    monkeypatch.setenv('OFFLINE_MODEL_KEY', 'offline-placeholder')
    monkeypatch.setattr(
        env.gateway.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs)
    )
    content = await env.gateway.ResearchModelGenerationService.generate_content(
        db, snapshot, job.materials, task_id=job.id
    )
    await db.commit()
    import json

    sent = json.loads(requests[0].content)
    assert content == '只来自离线供应商的正文' and requests[0].url.path == '/v1/chat/completions'
    assert snapshot['template']['prompt'] in sent['messages'][0]['content']
    assert '正文引用只放在句末' in sent['messages'][0]['content']
    assert '不要在句首或句中重复引用' in sent['messages'][0]['content']
    assert '不要附加来源类型和日期的括号说明' in sent['messages'][0]['content']
    assert job.materials[0]['content'] in sent['messages'][1]['content']
    assert sent['model'] == model.code
    assert db.s.scalars(select(env.configuration.PipelineModelCallAudit)).one().task_id == job.id


@pytest.mark.asyncio
async def test_edit_and_export_do_not_depend_on_review_or_publication(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    await env.app.ResearchApplicationService.update_report(
        db,
        user_id=7,
        owner_name='用户',
        report_id=result['reportId'],
        payload=NS(expected_version=1, expected_revision=None, content='# 正文', title=None),
    )
    export = await env.app.ResearchApplicationService.export_report(db, 7, result['reportId'])
    assert export['content'] == '# 正文' and export['fileName'] == '测试报告.md'
    assert not hasattr(env.app.ResearchApplicationService, 'publish_report')
    assert not hasattr(env.app.ResearchReportService, 'finalize_report')


@pytest.mark.asyncio
@pytest.mark.parametrize('original_form', ['scalar', 'typed'])
@pytest.mark.parametrize('replay_form', ['scalar', 'typed', 'snapshot'])
async def test_idempotent_reference_forms_replay_after_source_deleted(env, db, monkeypatch, original_form, replay_form):
    _, material = seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    scalar = payload()
    typed = payload(materials=[{'type': 'file', 'id': '101'}], selected_item_ids=[])
    original = await queue(env, db, scalar if original_form == 'scalar' else typed)
    job = await env.repo.ResearchDao.get_research_job(db, original['jobId'], 7)
    ids = importlib.import_module('app.business_ids')
    assert job.config_snapshot['request_fingerprint'] == ids.generation_request_fingerprint(
        job.config_snapshot['request'], job.materials
    )
    assert len(job.config_snapshot['request_fingerprint']) == 64
    assert 'materials' not in job.config_snapshot['request']
    assert job.config_snapshot['request']['selected_item_ids'] == [{'type': 'file', 'id': '101'}]
    replay = {
        'scalar': scalar,
        'typed': typed,
        'snapshot': {**deepcopy(job.config_snapshot['request']), 'request_id': 'same'},
    }[replay_form]
    await db.delete(material)
    await db.commit()
    jobs = importlib.import_module('app.research.services.jobs')
    resolve = AsyncMock(side_effect=AssertionError('replay must not reload deleted sources'))
    monkeypatch.setattr(jobs.ResearchEvidenceService, 'resolve', resolve)
    result = await queue(env, db, replay)
    assert result['reused'] and result['jobId'] == original['jobId']
    resolve.assert_not_awaited()
    assert len(db.s.scalars(select(env.models.PipelineResearchJob)).all()) == 1
    assert len(db.s.scalars(select(env.models.PipelineReport)).all()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['type', 'title', 'owner'])
async def test_replay_still_rejects_changed_semantics_or_owner_without_resolving(env, db, monkeypatch, change):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    await queue(env, db)
    jobs = importlib.import_module('app.research.services.jobs')
    resolve = AsyncMock(side_effect=AssertionError('conflicting replay must not resolve sources'))
    monkeypatch.setattr(jobs.ResearchEvidenceService, 'resolve', resolve)
    replay = payload()
    if change == 'type':
        replay.update(materials=[{'type': 'paper', 'id': '101'}], selected_item_ids=[])
    elif change == 'title':
        replay['title'] = '改变请求含义'
    with raises(env, '幂等键'):
        await queue(env, db, replay, user_id=8 if change == 'owner' else 7)
    resolve.assert_not_awaited()
    assert len(db.s.scalars(select(env.models.PipelineResearchJob)).all()) == 1


@pytest.mark.asyncio
async def test_request_id_race_recomputes_fingerprint_with_winners_frozen_materials(env, db, monkeypatch):
    _, material = seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    original = await queue(env, db, payload(materials=[{'type': 'file', 'id': '101'}], selected_item_ids=[]))
    material.edited_text = '并发请求解析到的更新正文'
    await db.commit()
    jobs = importlib.import_module('app.research.services.jobs')
    lookup = env.repo.ResearchDao.get_research_job_by_request_id
    calls = 0

    async def racing_lookup(session, request_id, *args, **kwargs):
        nonlocal calls
        calls += 1
        return None if calls == 1 else await lookup(session, request_id, *args, **kwargs)

    monkeypatch.setattr(env.repo.ResearchDao, 'get_research_job_by_request_id', racing_lookup)
    monkeypatch.setattr(
        env.repo.ResearchDao,
        'add_research_job',
        AsyncMock(side_effect=IntegrityError('request_id unique', {}, Exception('offline simulated race'))),
    )
    fingerprint = importlib.import_module('app.business_ids').generation_request_fingerprint
    bodies = []
    references = []

    def capture(request, materials):
        bodies.append([item['content'] for item in materials])
        references.append(deepcopy(request['selected_item_ids']))
        return fingerprint(request, materials)

    monkeypatch.setattr(jobs, 'generation_request_fingerprint', capture, raising=False)
    replay = await queue(env, db, payload())
    assert replay['reused'] and replay['jobId'] == original['jobId']
    assert bodies == [['并发请求解析到的更新正文'], ['原提取文本']]
    assert references == [['101'], ['101']]
    assert len(db.s.scalars(select(env.models.PipelineResearchJob)).all()) == 1
    assert len(db.s.scalars(select(env.models.PipelineReport)).all()) == 1
