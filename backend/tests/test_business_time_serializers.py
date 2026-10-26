"""Beijing audit display and opaque second-safe report revisions, offline only."""

import importlib
from copy import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import seed

env = memory_env
db = memory_db
no_external_network = offline_network
UTC_TIME = datetime(2026, 10, 25, 16, 0, 0, 999999, tzinfo=timezone.utc)
BEIJING_TEXT = '2026-10-26 00:00:00'


@pytest.mark.asyncio
async def test_report_material_template_ai_model_audit_serializers_use_beijing(env: Any, db: Any) -> None:
    template, file = seed(env, db)
    report = env.models.PipelineReport(user_id=7, title='报告', type='research', template_id=template.id,
                                       content='正文', version=1, created_at=UTC_TIME, updated_at=UTC_TIME)
    db.add(report)
    await db.flush()
    file.created_at = file.updated_at = template.updated_at = UTC_TIME
    report_dto = env.app.ResearchApplicationService.report_dict(report)
    assert report_dto['createdAt'] == report_dto['updatedAt'] == report_dto['updated_at'] == BEIJING_TEXT
    material = env.materials.MaterialService.material_dict(file, viewer_user_id=7)
    assert material['createdAt'] == material['updatedAt'] == BEIJING_TEXT
    assert env.template.PipelineTemplateService._dict(template)['updatedAt'] == BEIJING_TEXT
    model = await db.get(env.ai.AiModels, 1)
    model.created_at = model.updated_at = UTC_TIME
    ai_dto = env.ai_service.AiModelService.public(model)
    assert ai_dto.model_dump(by_alias=True)['createdAt'] == BEIJING_TEXT
    assert ai_dto.model_dump(mode='json', by_alias=True)['updatedAt'] == BEIJING_TEXT
    assert ai_dto.created_at is UTC_TIME  # DTO internals remain datetime, not display text.
    job = env.models.PipelineResearchJob(report_id=report.id, request_id='manual:beijing-audit', materials=[],
                                         config_snapshot={}, created_at=UTC_TIME, updated_at=UTC_TIME)
    db.add(job)
    await db.flush()
    job_dto = env.app.ResearchApplicationService.job_dict(job, report=report)
    assert job_dto['createdAt'] == job_dto['updatedAt'] == BEIJING_TEXT


def test_revision_hash_covers_persisted_row_state_and_ignores_datetime_microseconds() -> None:
    revision = importlib.import_module('app.research.services.report_revision').report_revision
    row = SimpleNamespace(id=301, user_id=7, title='标题', type='research', template_id=201,
                           content='正文', version=1, created_at=UTC_TIME, updated_at=UTC_TIME)
    token = revision(row)
    assert token and token != UTC_TIME.isoformat()
    rounded = copy(row)
    rounded.created_at = rounded.updated_at = UTC_TIME.replace(microsecond=0)
    assert revision(rounded) == token
    local_wall = copy(rounded)
    local_wall.created_at = local_wall.updated_at = rounded.updated_at.astimezone(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None)
    assert revision(local_wall) == token
    for field in ('created_at', 'updated_at'):
        changed = copy(row)
        setattr(changed, field, getattr(row, field) + timedelta(seconds=1))
        assert revision(changed) != token
    for name, value in {'id': 302, 'user_id': 8, 'title': '新标题', 'type': 'article', 'template_id': 202,
                        'content': '同秒另一正文', 'version': 2}.items():
        changed = copy(row)
        setattr(changed, name, value)
        assert revision(changed) != token, name


@pytest.mark.asyncio
async def test_same_second_stale_revision_rejected_and_fresh_roundtrip_revision_accepted(
    env: Any, db: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    template, _ = seed(env, db)
    instant = UTC_TIME.replace(microsecond=0)
    report = env.models.PipelineReport(user_id=7, title='原始', type='research', template_id=template.id,
                                       content='原始正文', version=1, created_at=instant, updated_at=instant)
    db.add(report)
    await db.commit()
    reports = importlib.import_module('app.research.services.reports')
    monkeypatch.setattr(reports, 'utcnow', lambda: instant)
    monkeypatch.setattr(env.models.PipelineReport.__table__.c.updated_at.onupdate, 'arg', lambda context: instant)
    serializer = env.app.ResearchApplicationService.report_dict
    original = serializer(report)
    first = await env.app.ResearchApplicationService.update_report(
        db, user_id=7, owner_name='第一位', report_id=report.id,
        payload=SimpleNamespace(expected_version=1, expected_revision=original['revision'], content='同秒第一次编辑'))
    assert first['updatedAt'] == original['updatedAt']
    assert first['revision'] != original['revision']
    with pytest.raises(env.exc) as caught:
        await env.app.ResearchApplicationService.update_report(
            db, user_id=7, owner_name='过期编辑者', report_id=report.id,
            payload=SimpleNamespace(expected_version=2, expected_revision=original['revision'], content='不能覆盖'))
    assert '修订' in caught.value.message
    db.s.expire_all()
    refreshed = serializer(await env.repo.ResearchDao.get_report(db, report.id, 7))
    assert refreshed['revision'] == first['revision']
    saved = await env.app.ResearchApplicationService.update_report(
        db, user_id=7, owner_name='刷新后的编辑者', report_id=report.id,
        payload=SimpleNamespace(expected_version=2, expected_revision=refreshed['revision'], content='同秒第二次编辑'))
    assert saved['content'] == '同秒第二次编辑' and saved['versionNo'] == refreshed['versionNo'] + 1


def test_report_history_and_export_audit_timestamps_use_beijing(env: Any) -> None:
    history = SimpleNamespace(id=1, report_id=301, version=1, title='历史', content='正文', source='manual',
                               sections=[], citations=[], quality_issues=[], operator_name='操作者', created_at=UTC_TIME)
    assert env.app.ResearchReportService.version_dict(history)['createdAt'] == BEIJING_TEXT
    exports = importlib.import_module('app.research.services.exports')
    asset = SimpleNamespace(id=1, report_id=301, task_id=None, type='export', mime_type='application/pdf',
                             status='queued', config_snapshot={'version': 1}, error=None, created_at=UTC_TIME)
    assert exports.ResearchReportExportService._record_dict(asset)['createdAt'] == BEIJING_TEXT
