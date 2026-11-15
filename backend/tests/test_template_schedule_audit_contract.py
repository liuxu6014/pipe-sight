"""Regression checks for explicit cadence, scoped paging and schedule recovery."""

from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from test_digest_schedule_generation_guard import dispatch_fixture, setup_template
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network

env, db, no_external_network = memory_env, memory_db, offline_network


@pytest.mark.asyncio
async def test_digest_format_has_fixed_cadence_and_rejects_personal_override(env, db):
    service = env.template.PipelineTemplateService
    row = await service.get_fixed_digest(db, 'monthly', 7)
    service.validate_digest_cadence(row, 'monthly')
    with pytest.raises(env.exc):
        service.validate_digest_cadence(row, 'weekly')
    row.name, row.prompt, row.sections = '旧客户端修改', '不可信的提示词', [{'title': '不应使用的章节'}]
    restored = await service.get_fixed_digest(db, 'monthly', 7)
    assert restored.id == row.id and restored.name == '管网科技情报月报'
    assert restored.prompt != '不可信的提示词' and restored.sections == []


@pytest.mark.asyncio
async def test_template_pages_are_owner_scoped_stable_filtered_and_omit_prompts(env, db):
    service = env.template.PipelineTemplateService
    for user_id, count in ((7, 25), (8, 4)):
        for index in range(count):
            db.add(
                env.configuration.PipelineTemplateVersion(
                    user_id=user_id,
                    name=f'模板{index:02}',
                    purpose='research',
                    report_type='research-demand',
                    prompt='私人提示词' * 1000,
                    sections=[],
                    image_config={},
                    is_enabled=True,
                    updated_at=datetime(2026, 11, 15),
                )
            )
    await service.get_fixed_digest(db, 'weekly', 7)
    await service.get_fixed_digest(db, 'monthly', 7)
    await db.commit()
    first = await service.list_templates(db, user_id=7, page=1, page_size=10)
    second = await service.list_templates(db, user_id=7, page=2, page_size=10)
    assert first['total'] == second['total'] == 25
    assert first['counts'] == {'all': 25, 'research-demand': 25}
    assert len(first['rows']) == len(second['rows']) == 10
    assert not ({row['id'] for row in first['rows']} & {row['id'] for row in second['rows']})
    assert all('prompt' not in row for row in first['rows'])
    assert [row['name'] for row in first['rows']] == [f'模板{i:02}' for i in range(24, 14, -1)]
    filtered = await service.list_templates(db, user_id=8, page=1, keyword='模板02')
    assert filtered['total'] == 1 and filtered['rows'][0]['name'] == '模板02'
    assert (await service.list_templates(db, user_id=7, page=1, keyword='%'))['total'] == 0


@pytest.mark.asyncio
async def test_digest_formats_remain_read_only_even_after_schedules_are_stopped(env, db):
    template, _ = await setup_template(env, db)
    row = env.models.PipelineDigestSchedule(
        user_id=7,
        template_id=template.id,
        name='管网周报任务',
        frequency='weekly',
        weekday=0,
        run_time=time(9),
        selection_config={},
        generation_config={},
        is_enabled=True,
        next_run_at=datetime(2026, 11, 16, tzinfo=timezone.utc),
    )
    db.add(row)
    await db.commit()
    service = env.template.PipelineTemplateService
    for enabled in (True, False):
        row.is_enabled = enabled
        await db.commit()
        for action in ('retire', 'archive'):
            with pytest.raises(env.exc):
                await getattr(service, action)(db, template.id, user_id=7)
            assert template.is_enabled and template.deleted_at is None


@pytest.mark.asyncio
async def test_transient_dispatch_failure_backs_off_without_losing_business_period(env, db, monkeypatch):
    await setup_template(env, db)
    service = env.schedules.DigestScheduleService
    validate = AsyncMock(side_effect=RuntimeError('temporary unavailable'))
    monkeypatch.setattr(service, '_validate_enabled_template', validate)
    result, row, queue, _, due = await dispatch_fixture(env, db, monkeypatch, {})
    assert result['failed'] == 1 and row.is_enabled
    retry = env.repo.ResearchDao.aware(row.next_retry_at)
    assert retry is not None and row.retry_count == 1
    assert env.repo.ResearchDao.aware(row.next_run_at) == due
    result = await service.dispatch_due(
        stage_labels=[], job_serializer=dict, template_service=env.template.PipelineTemplateService
    )
    assert result['found'] == 0
    assert validate.await_count == 1
    monkeypatch.setattr(env.schedules.research_models, 'utcnow', lambda: retry + timedelta(seconds=1))
    validate.side_effect = None
    result = await service.dispatch_due(
        stage_labels=[], job_serializer=dict, template_service=env.template.PipelineTemplateService
    )
    assert result['no_data'] == 1 and row.retry_count == 0 and row.next_retry_at is None
    assert env.repo.ResearchDao.aware(row.next_run_at) > due
    queue.assert_not_awaited()
