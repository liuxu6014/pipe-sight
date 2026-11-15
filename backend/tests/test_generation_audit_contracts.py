"""Audit F03/F04/F08: deterministic manuscript contracts and bounded dispatch."""

import asyncio
import importlib
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import seed

env = memory_env
db = memory_db
no_external_network = offline_network


@pytest.mark.parametrize('kind', ['research-demand', 'technology-route', 'project-demand'])
@pytest.mark.parametrize('titles', [['无关小节'], ['研究内容', '研究目标'], ['研究目标', '研究内容', '多余章节']])
def test_missing_wrong_order_or_extra_chapters_fail_for_all_research_types(env, kind, titles):
    service = importlib.import_module('app.research.services.report_content')
    snapshot = {'type': kind, 'request': {'outline': [{'title': '研究目标'}, {'title': '研究内容'}]}}
    raw = '\n\n'.join(f'**{title}**\n\n真正的正文。' for title in titles)
    with pytest.raises(service.ManuscriptValidationError, match='章节或顺序'):
        service.normalize_task_report(raw, [], snapshot)


def test_outline_length_has_hard_short_gate_and_explicit_soft_warning(env):
    service = importlib.import_module('app.research.services.report_content')
    snapshot = {'request': {'outline': [{'title': '研究目标', 'words': 1000}]}}
    with pytest.raises(service.ManuscriptValidationError, match='正文过短'):
        service.normalize_task_report('**研究目标**\n\n极短正文。', [], snapshot)
    result = service.normalize_task_report('**一、研究目标**\n\n' + '研究目标' * 100, [], snapshot)
    assert result['qualityIssues'][0]['code'] == 'chapter_length_deviation'
    assert result['qualityIssues'][0]['actualWords'] == 400
    assert service.normalize_task_report('**研究目标**\n\n' + '研究目标' * 250, [], snapshot)['qualityIssues'] == []


@pytest.mark.parametrize('kind', ['research-demand', 'technology-route', 'project-demand'])
def test_standalone_document_title_is_not_an_extra_chapter_but_prose_is_never_dropped(env, kind):
    service = importlib.import_module('app.research.services.report_content')
    titles = [f'确认章节{index}' for index in range(1, 8)]
    snapshot = {'type': kind, 'request': {'outline': [{'title': title} for title in titles]}}
    body = '\n\n'.join(f'**{title}**\n\n本章真实正文。' for title in titles)
    result = service.normalize_task_report('**模型拟定的报告总标题**\n\n' + body, [], snapshot)
    assert [s['title'] for s in result['sections']] == titles
    assert result['content'] == body
    for prefix in ['**额外章节**\n\n不能丢弃的正文。\n\n', '**总标题**\n\n**另一标题**\n\n']:
        with pytest.raises(service.ManuscriptValidationError, match='章节或顺序'):
            service.normalize_task_report(prefix + body, [], snapshot)


@pytest.mark.parametrize('status', ['failed', 'cancelled'])
def test_unsuccessful_task_with_raw_output_never_claims_saved_report_result(env, status):
    job = NS(status=status, result_content='被校验拒绝的原始模型输出', created_at=None, started_at=None,
             finished_at=None, updated_at=None, config_snapshot={}, error='正文与大纲不一致')
    result = env.app.ResearchApplicationService._execution_display(job)
    saved = next(stage for stage in result['stages'] if stage['key'] == 'result')
    assert saved['status'] == 'skipped'
    assert saved['description'] == '原始输出已保留，未应用为报告正文'


def test_citation_check_maps_each_sentence_and_flags_unresolved_or_unused_sources(env):
    service = importlib.import_module('app.research.services.report_content')
    sources = [{'id': 101, 'type': 'article'}, {'id': 102, 'type': 'paper'}]
    text = '**研究内容**\n\n第一处观点[1]。第二处观点[1]。\n\n**参考资料**\n\n[1] 来源甲\n[2] 来源乙'
    result = service.check_citation_integrity(text, sources)
    assert result['status'] == 'warning' and result['factsVerified'] is False
    assert [item['quote'] for item in result['occurrences']] == ['第一处观点[1]。', '第二处观点[1]。']
    assert [item['offset'] for item in result['occurrences']] == [5, 14]
    assert result['issues'] == [{'code': 'unused_sources', 'message': '部分来源未在正文中引用', 'citationIds': [2]}]
    failed = service.check_citation_integrity('**正文**\n\n无法定位[9]。', sources)
    assert failed['status'] == 'failed' and failed['issues'][0]['code'] == 'unresolved_citation'
    assert (
        service.check_citation_integrity('**正文**\n\n仅有[1](https://example.org)普通链接。', sources)['status']
        == 'failed'
    )


@pytest.mark.asyncio
async def test_versioned_checks_become_stale_on_manual_edit_without_mutating_old_snapshot(env, monkeypatch):
    service = importlib.import_module('app.research.services.execution')
    checks = {
        'citation': {'status': 'passed', 'version': 1, 'requested': True},
        'quality': {'status': 'not_run', 'version': 1},
    }
    old = NS(model_snapshot={'checks': deepcopy(checks)}, sections=[], citations=[], quality_issues=[])
    monkeypatch.setattr(env.repo.ResearchDao, 'get_report_version', AsyncMock(side_effect=[None, old]))
    add = AsyncMock()
    monkeypatch.setattr(env.repo.ResearchDao, 'add_report_version', add)
    report = NS(id=301, version=2, title='编辑后', content='新的正文', template_id=None)
    await service.ResearchExecutionService.save_version(None, report, 'manual', 7, '用户')
    current = add.await_args.args[1].model_snapshot['checks']['citation']
    assert current['status'] == 'stale' and current['version'] == 2 and current['checkedVersion'] == 1
    assert old.model_snapshot['checks'] == checks


def add_job(env, db, number, user, *, model=1, status='queued', created=None):
    now = env.models.utcnow()
    report = env.models.PipelineReport(
        id=300 + number, user_id=user, title=f'任务{number}', type='research', content=''
    )
    job = env.models.PipelineResearchJob(
        id=400 + number,
        report_id=report.id,
        request_id=f'audit:{number}',
        status=status,
        created_at=created or now,
        config_snapshot={'model': {'id': str(model)}},
        materials=[],
        lease_expires_at=now + timedelta(minutes=5) if status == 'running' else None,
    )
    db.add(report)
    db.add(job)
    return job


@pytest.mark.asyncio
async def test_dispatch_query_is_bounded_and_rotates_between_users(env, db):
    seed(env, db)
    now = env.models.utcnow()
    for index in range(1, 5):
        add_job(env, db, index, 7, created=now - timedelta(minutes=5 - index))
    add_job(env, db, 5, 8, created=now)
    await db.commit()
    rows = await env.repo.ResearchDao.list_research_job_ids_for_dispatch(db, now=now, limit=2)
    assert [(row[0], row[1]) for row in rows] == [(401, 7), (405, 8)]
    rows = await env.repo.ResearchDao.list_research_job_ids_for_dispatch(db, now=now, limit=1, exclude_ids=[401])
    assert len(rows) == 1 and rows[0][0] != 401


@pytest.mark.asyncio
async def test_database_claim_respects_user_and_model_capacity_without_consuming_attempts(env, db, monkeypatch):
    capacity = importlib.import_module('app.research.services.concurrency')
    monkeypatch.setattr(capacity, 'RESEARCH_GLOBAL_LIMIT', 4)
    monkeypatch.setattr(capacity, 'RESEARCH_USER_LIMIT', 1)
    monkeypatch.setattr(capacity, 'RESEARCH_MODEL_LIMIT', 1)
    seed(env, db)
    add_job(env, db, 1, 7, status='running')
    add_job(env, db, 2, 7)
    add_job(env, db, 3, 8)
    add_job(env, db, 4, 8, model=2)
    await db.commit()
    assert await env.repo.ResearchDao.claim_research_job(db, 402, 7) is None
    assert await env.repo.ResearchDao.claim_research_job(db, 403, 8) is None
    allowed = await env.repo.ResearchDao.claim_research_job(db, 404, 8)
    assert allowed.status == 'running' and allowed.attempts == 1
    blocked = await env.repo.ResearchDao.get_research_job(db, 402, 7)
    assert blocked.status == 'queued' and blocked.attempts == 0


@pytest.mark.asyncio
async def test_full_model_does_not_hide_ready_work_for_another_model(env, db, monkeypatch):
    capacity = importlib.import_module('app.research.services.concurrency')
    monkeypatch.setattr(capacity, 'RESEARCH_GLOBAL_LIMIT', 4)
    monkeypatch.setattr(capacity, 'RESEARCH_USER_LIMIT', 2)
    monkeypatch.setattr(capacity, 'RESEARCH_MODEL_LIMIT', 1)
    seed(env, db)
    add_job(env, db, 1, 7, status='running')
    for number in range(2, 45):
        add_job(env, db, number, 7)
    add_job(env, db, 45, 8, model=2)
    await db.commit()
    rows = await env.repo.ResearchDao.list_research_job_ids_for_dispatch(db, now=env.models.utcnow(), limit=2)
    assert rows == [(445, 8, '')]


@pytest.mark.asyncio
async def test_fifty_pending_jobs_never_start_fifty_tasks(env, monkeypatch):
    scheduler = importlib.import_module('app.research.tasks.research_job_scheduler')
    release = asyncio.Event()
    started = []

    async def work(**kwargs):
        started.append(kwargs['job_id'])
        await release.wait()

    @asynccontextmanager
    async def session():
        yield NS()

    monkeypatch.setattr(scheduler, 'AsyncSessionLocal', session)
    listing = AsyncMock(return_value=[(number, number, '') for number in range(1, 51)])
    monkeypatch.setattr(scheduler.PipelineDao, 'list_research_job_ids_for_dispatch', listing)
    monkeypatch.setattr(scheduler.ResearchApplicationService, 'process_queued_job', work)
    scheduler._recovery_tasks.clear()
    scheduler._recovery_owners.clear()
    try:
        first = await scheduler.recover_research_jobs()
        await asyncio.sleep(0)
        second = await scheduler.recover_research_jobs()
        assert first['dispatched'] == scheduler.RESEARCH_GLOBAL_LIMIT
        assert len(started) == scheduler.RESEARCH_GLOBAL_LIMIT
        assert second['dispatched'] == 0
        assert listing.await_args.kwargs['limit'] == scheduler.RESEARCH_DISPATCH_BATCH
    finally:
        release.set()
        await scheduler.stop_recovery_tasks()
