from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from test_digest_schedule_generation_guard import dispatch_fixture, setup_template
from test_research_simplified_20261025 import db as memory_db, env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network

env, db, no_external_network = memory_env, memory_db, offline_network


@pytest.mark.asyncio
async def test_no_match_dispatch_persists_summary_without_job(env, db, monkeypatch):
    await setup_template(env, db)
    result, row, queue, _, _ = await dispatch_fixture(env, db, monkeypatch, {})
    assert result['no_data'] == 1
    db.s.refresh(row)
    assert row.last_status == 'no_data'
    assert row.last_run_at is not None
    assert row.last_error is None
    queue.assert_not_awaited()
    data = env.schedules.DigestScheduleService.serialize(row)
    assert data['lastStatus'] == 'no_data' and data['matchedCount'] == 0
    assert data['lastRunTime'] and not data['hasResult']


@pytest.mark.asyncio
async def test_dispatch_failure_preserves_cursor_and_records_safe_reason(env, db, monkeypatch):
    await setup_template(env, db)
    result, row, _, _, before = await dispatch_fixture(env, db, monkeypatch, {'unknown_setting': []})
    assert result['failed'] == 1
    assert env.repo.ResearchDao.aware(row.next_run_at) == before
    assert row.last_status == 'failed' and row.last_error
    assert env.schedules.DigestScheduleService.serialize(row)['lastError']


@pytest.mark.asyncio
async def test_holiday_skip_is_recorded_without_model_or_queue(env, db, monkeypatch):
    await setup_template(env, db)
    result,row,queue,query,_ = await dispatch_fixture(env,db,monkeypatch,{},
        selection_config={'holiday_policy':'skip','holiday_dates':['2026-10-25']})
    assert result['skipped'] == 1 and row.last_status == 'skipped'
    assert row.last_run_at and row.last_error is None
    queue.assert_not_awaited()
    query.assert_not_awaited()


def test_errors_redact_credentials_without_losing_actionable_reason(env):
    error = env.schedules.DigestScheduleService.safe_error('模型认证失败\napi_key=private-secret Bearer abcdef sk-test123')
    assert '模型认证失败' in error
    for value in ['private-secret','abcdef','sk-test123']:
        assert value not in error


@pytest.mark.asyncio
async def test_history_uses_existing_task_without_backfilling_and_new_skip_wins(env, db):
    template, _ = await setup_template(env, db)
    service = env.schedules.DigestScheduleService
    created = await service.create(db, user_id=7, owner_name='', template_service=env.template.PipelineTemplateService,
        payload={'name': '历史计划', 'template_id': str(template.id), 'report_type': 'daily', 'enabled': False})
    row = (await env.repo.ResearchDao.list_digest_schedules(db, 7))[0]
    report = SimpleNamespace(id=801, title='已有简报', content='真实正文')
    job = SimpleNamespace(id=802, status='completed', materials=[{'id': '1'}], error=None,
        created_at=datetime(2026,10,27,tzinfo=timezone.utc), started_at=None, finished_at=None, progress=100)
    data = service.serialize(row, latest_job=job, report=report)
    assert data['lastStatus'] == 'completed' and data['hasResult']
    assert data['latestTaskId'] == '802' and data['latestReportId'] == '801'
    assert data['matchedCount'] == 1
    assert row.last_status is None and row.last_run_at is None
    row.last_status, row.last_run_at = 'no_data', datetime(2026,10,28,tzinfo=timezone.utc)
    data = service.serialize(row, latest_job=job, report=report)
    assert data['lastStatus'] == 'no_data' and not data['hasResult']
    assert data['latestReportId'] == ''
    assert created['lastStatus'] == 'never'


@pytest.mark.asyncio
async def test_latest_history_is_owner_scoped_and_links_only_nonempty_completed_results(env, db):
    template, _ = await setup_template(env, db)
    service = env.schedules.DigestScheduleService
    created = await service.create(db, user_id=7, owner_name='', template_service=env.template.PipelineTemplateService,
        payload={'name':'计划', 'template_id':str(template.id), 'report_type':'daily', 'enabled':False})
    report = env.models.PipelineReport(id=901,user_id=7,title='已有结果',type='daily',template_id=template.id,content='正文')
    db.add(report)
    await db.commit()
    for ident, status in [(902,'failed'), (903,'completed')]:
        db.add(env.models.PipelineResearchJob(id=ident,report_id=901,schedule_id=int(created['id']),
            request_id=str(ident),status=status,materials=[{'id':'11'}],config_snapshot={}))
    await db.commit()
    data = await service.list(db, 7)
    assert data['rows'][0]['latestTaskId'] == '903'
    assert data['rows'][0]['latestReportId'] == '901'
    assert data['rows'][0]['canDelete'] is False
    assert (await service.list(db,8))['rows'] == []
    report.content = ''
    await db.commit()
    assert not (await service.list(db,7))['rows'][0]['hasResult']
