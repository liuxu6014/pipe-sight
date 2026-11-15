"""F09: real SQL pagination, owner boundaries and narrow read DTOs."""

import importlib
from datetime import timedelta

import pytest
from sqlalchemy import update
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import seed

env = memory_env
db = memory_db
no_external_network = offline_network


def add_report(env, db, index, owner=7, *, content='正文不得全量返回' * 400, report_type='research'):
    now = env.models.utcnow() + timedelta(minutes=index)
    row = env.models.PipelineReport(
        id=1000 + index,
        user_id=owner,
        title=f'报告{index:03}',
        type=report_type,
        content=content,
        version=2,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.s.flush()
    for version in (1, 2):
        db.add(
            env.models.PipelineReportVersion(
                report_id=row.id,
                version=version,
                title=row.title,
                content=row.content,
                source='generated',
                operator_id=owner,
                sections=[],
                citations=[],
                quality_issues=[],
                model_snapshot={
                    'privatePrompt': '提示词不可进入列表',
                    'request': {'period': ['2026-10-01', '2026-10-31']},
                },
            )
        )
    return row


@pytest.mark.asyncio
async def test_report_pages_have_correct_totals_stable_sort_and_no_cross_account_rows(env, db):
    seed(env, db)
    for index in range(1, 24):
        add_report(env, db, index)
    for index in range(30, 34):
        add_report(env, db, index, 8)
    await db.commit()
    lists = importlib.import_module('app.research.services.list_queries')
    pages = [await lists.report_page(db, user_id=7, page=page, page_size=10) for page in (1, 2, 3)]
    assert [len(page['rows']) for page in pages] == [10, 10, 3]
    assert all(page['total'] == 23 for page in pages)
    ids = [row['id'] for page in pages for row in page['rows']]
    assert ids == [str(1000 + index) for index in range(23, 0, -1)]
    assert len(ids) == len(set(ids))
    for page in pages:
        for row in page['rows']:
            assert row['ownerId'] == 7
            assert not {'content', 'sections', 'citations', 'configSnapshot', 'modelSnapshot'} & row.keys()
            assert row['metadata'] == {'period': ['2026-10-01', '2026-10-31']}
    asc = await lists.report_page(db, user_id=7, page_size=100, sort='updated-asc')
    assert [row['id'] for row in asc['rows']] == list(reversed(ids))
    title = await lists.report_page(db, user_id=7, page_size=2, sort='title-desc')
    assert [row['title'] for row in title['rows']] == ['报告023', '报告022']
    all_users = await lists.report_page(db, page_size=10)
    assert all_users['total'] == 27


@pytest.mark.asyncio
async def test_latest_generation_status_filters_and_escaped_keyword_are_correct(env, db):
    seed(env, db)
    # A regeneration may queue behind an already usable report. It remains a
    # generated list entry, rather than leaking into the empty queued group.
    for index, status in [(1, 'queued'), (2, 'queued'), (3, 'failed'), (4, 'cancelled'), (7, 'running')]:
        row = add_report(env, db, index, content='已生成正文' if index == 1 else '')
        db.add(
            env.models.PipelineResearchJob(
                id=2000 + index,
                report_id=row.id,
                request_id=f'new:{index}',
                status=status,
                progress=25,
                config_snapshot={},
                materials=[],
            )
        )
        if index == 3:
            db.add(
                env.models.PipelineResearchJob(
                    id=3000 + index,
                    report_id=row.id,
                    request_id=f'old:{index}',
                    status='completed',
                    created_at=env.models.utcnow() - timedelta(days=1),
                    config_snapshot={},
                    materials=[],
                )
            )
    special = add_report(env, db, 5)
    special.title = '100%有效'
    sibling = add_report(env, db, 6)
    sibling.title = '100x有效'
    await db.commit()
    lists = importlib.import_module('app.research.services.list_queries')
    for status, expected in [
        ('generated', [1006, 1005, 1001]),
        ('active', [1002, 1007]),
        ('queued', [1002]),
        ('running', [1007]),
        ('failed', [1003]),
        ('cancelled', [1004]),
    ]:
        result = await lists.report_page(db, user_id=7, status=status)
        assert result['total'] == len(expected)
        assert {int(row['id']) for row in result['rows']} == set(expected)
        if status in {'queued', 'running'}:
            assert result['rows'][0]['status'] == status
            assert result['rows'][0]['listStatus'] == 'active'
    result = await lists.report_page(db, user_id=7, keyword='100%')
    assert result['total'] == 1 and result['rows'][0]['title'] == '100%有效'
    db.s.execute(update(env.SysUser).where(env.SysUser.id == 7).values(nickname='作者甲'))
    await db.commit()
    assert (await lists.report_page(db, user_id=7, keyword='作者甲'))['total'] == 7


@pytest.mark.asyncio
async def test_digest_period_overlap_and_type_filter_do_not_return_research_reports(env, db):
    seed(env, db)
    add_report(env, db, 1, report_type='weekly')
    add_report(env, db, 2, report_type='monthly')
    add_report(env, db, 3)
    daily = add_report(env, db, 4, report_type='daily')
    history = await env.repo.ResearchDao.get_report_version(db, daily.id, 2)
    history.model_snapshot = {'request': {'period': ['2026-09-30']}}
    await db.commit()
    lists = importlib.import_module('app.research.services.list_queries')
    result = await lists.report_page(db, user_id=7, kind='digest', start='2026-10-15', end='2026-11-01')
    assert result['total'] == 2 and {row['type'] for row in result['rows']} == {'weekly', 'monthly'}
    assert (await lists.report_page(db, user_id=7, kind='weekly'))['total'] == 1
    assert (await lists.report_page(db, user_id=7, kind='digest', start='2026-11-01'))['total'] == 0
    legacy = await lists.report_page(db, user_id=7, kind='daily', start='2026-09-30', end='2026-09-30')
    assert legacy['total'] == 1 and legacy['rows'][0]['period'] == ['2026-09-30']
    current = await lists.report_page(db, user_id=7, kind='brief')
    assert current['total'] == 2 and {row['type'] for row in current['rows']} == {'weekly', 'monthly'}
    historical = await lists.report_page(db, kind='digest')
    assert historical['total'] == 3 and {row['type'] for row in historical['rows']} == {'daily', 'weekly', 'monthly'}


@pytest.mark.asyncio
async def test_material_pages_filter_owner_status_keyword_and_only_send_short_summary(env, db):
    seed(env, db)
    # seed() already creates one ready material, which is deliberately retained.
    for index in range(1, 25):
        now = env.models.utcnow() + timedelta(minutes=index)
        row = env.material.PipelineMaterial(
            id=1000 + index,
            user_id=7 if index < 23 else 8,
            name=f'资料{index:03}',
            filename=f'material-{index}.txt',
            storage_key=f'private/{index}',
            mime_type='text/plain',
            size=5000,
            hash=str(index).zfill(64),
            extracted_text='资料正文禁止全量返回' * 500,
            status='ready' if index % 2 else 'queued',
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    await db.commit()
    lists = importlib.import_module('app.research.services.list_queries')
    pages = [await lists.material_page(db, user_id=7, page=page, page_size=10) for page in (1, 2, 3)]
    assert all(page['total'] == 23 for page in pages)
    assert [len(page['rows']) for page in pages] == [10, 10, 3]
    ids = [row['id'] for page in pages for row in page['rows']]
    assert len(ids) == len(set(ids)) == 23
    for page in pages:
        for row in page['rows']:
            assert row['ownerId'] == 7 and len(row['summary']) <= 240
            assert not {'content', 'extracted_text', 'edited_text', 'storageKey', 'storage_key'} & row.keys()
    assert (await lists.material_page(db, user_id=7, status='处理中'))['total'] == 11
    assert (await lists.material_page(db, user_id=7, status='已解析'))['total'] == 12
    assert (await lists.material_page(db, user_id=7, keyword='资料022'))['total'] == 1
    assert (await lists.material_page(db, user_id=7, keyword='资料023'))['total'] == 0
    assert (await lists.material_page(db, user_id=7, keyword='禁止全量'))['total'] == 22
