"""Deletion uses offline SQLite with real foreign keys; no application data is touched."""

import importlib

import pytest
from sqlalchemy import select
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as isolated_env
from test_research_simplified_20261025 import no_external_network, seed  # noqa: F401

env = isolated_env
db = memory_db


def setup_reports(env, db, *, job_status='completed', asset_status='completed'):
    seed(env, db)
    for identity in (401, 402):
        db.add(
            env.models.PipelineReport(id=identity, user_id=7, title=f'报告{identity}', type='research', content='正文')
        )
    db.s.flush()
    for identity in (401, 402):
        db.add(
            env.models.PipelineResearchJob(
                id=identity + 10,
                report_id=identity,
                request_id=f'delete-{identity}',
                status=job_status if identity == 401 else 'completed',
            )
        )
        db.add(
            env.models.PipelineReportVersion(
                report_id=identity,
                version=1,
                title='报告',
                content='正文',
                sections=[],
                citations=[{'itemId': '101'}],
                quality_issues=[],
                model_snapshot={},
            )
        )
        db.add(env.models.PipelineWorkspaceItem(user_id=7, report_id=identity, action='favorite'))
    db.s.flush()
    for identity in (401, 402):
        db.add(
            env.models.PipelineReportAsset(
                id=identity + 20,
                report_id=identity,
                task_id=identity + 10,
                type='export',
                mime_type='application/pdf',
                storage_key=f'offline/{identity}.pdf',
                status=asset_status if identity == 401 else 'completed',
            )
        )
    db.s.commit()
    return importlib.import_module('app.research.services.reports').ResearchReportService


@pytest.mark.asyncio
async def test_delete_is_owner_scoped_and_removes_only_target_dependencies(env, db):
    service = setup_reports(env, db)
    with pytest.raises(env.exc) as exc:
        await service.delete_report(db, user_id=8, report_id=401)
    assert '无权访问' in exc.value.message
    assert await db.get(env.models.PipelineReport, 401)
    result = await service.delete_report(db, user_id=7, report_id=401)
    assert result == {'id': '401'}
    db.s.expire_all()
    assert await db.get(env.models.PipelineReport, 401) is None
    assert await db.get(env.models.PipelineReport, 402)
    for model in (
        env.models.PipelineResearchJob,
        env.models.PipelineReportVersion,
        env.models.PipelineReportAsset,
        env.models.PipelineWorkspaceItem,
    ):
        assert list(await db.scalars(select(model.report_id))) == [402]
    assert (await db.get(env.material.PipelineMaterial, 101)).extracted_text == '原提取文本'
    with pytest.raises(env.exc):
        await service.delete_report(db, user_id=7, report_id=401)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('job_status', 'asset_status', 'message'),
    [
        ('queued', 'completed', '生成任务'),
        ('running', 'completed', '生成任务'),
        ('completed', 'queued', '导出或配图'),
        ('completed', 'running', '导出或配图'),
    ],
)
async def test_running_work_blocks_delete_without_changing_records(env, db, job_status, asset_status, message):
    service = setup_reports(env, db, job_status=job_status, asset_status=asset_status)
    with pytest.raises(env.exc) as exc:
        await service.delete_report(db, user_id=7, report_id=401)
    assert message in exc.value.message
    assert (await db.get(env.models.PipelineReport, 401)).content == '正文'
    assert len(list(await db.scalars(select(env.models.PipelineReportAsset)))) == 2
