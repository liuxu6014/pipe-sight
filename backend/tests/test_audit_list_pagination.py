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
async def test_generation_time_uses_successful_completion_and_survives_later_edits_or_failed_retries(env, db):
    seed(env, db)
    report = add_report(env, db, 1, report_type='weekly')
    now = env.models.utcnow()
    completed = now - timedelta(days=1)
    for index, status, stamp, content in [
        (1, 'completed', completed - timedelta(hours=1), '初次正文'),
        (2, 'completed', completed, '生成正文'),
        (3, 'failed', now, None),
        (4, 'completed', now, ''),
    ]:
        db.add(
            env.models.PipelineResearchJob(
                id=2000 + index,
                report_id=report.id,
                request_id=f'generation-time:{index}',
                status=status,
                progress=100 if status == 'completed' else 0,
                finished_at=stamp,
                result_content=content,
                config_snapshot={},
                materials=[],
            )
        )
    report.updated_at = now + timedelta(hours=1)
    await db.commit()
    lists = importlib.import_module('app.research.services.list_queries')
    from app.business_time import format_business_time

    row = (await lists.report_page(db, user_id=7, kind='weekly'))['rows'][0]
    assert row['generatedAt'] == format_business_time(completed)
    assert row['generatedAt'] != row['updatedAt']


@pytest.mark.asyncio
async def test_legacy_generation_time_uses_original_generated_version_and_empty_reports_have_no_time(env, db):
    seed(env, db)
    report = add_report(env, db, 1, report_type='weekly')
    pending = add_report(env, db, 2, content='', report_type='weekly')
    generated = env.models.utcnow() - timedelta(days=2)
    original = await env.repo.ResearchDao.get_report_version(db, report.id, 1)
    original.created_at = generated
    edited = await env.repo.ResearchDao.get_report_version(db, report.id, 2)
    edited.source = 'user'
    edited.created_at = generated + timedelta(days=1)
    await db.commit()
    lists = importlib.import_module('app.research.services.list_queries')
    from app.business_time import format_business_time

    rows = {row['id']: row for row in (await lists.report_page(db, user_id=7, kind='weekly'))['rows']}
    assert rows[str(report.id)]['generatedAt'] == format_business_time(generated)
    assert rows[str(pending.id)]['generatedAt'] == ''


@pytest.mark.asyncio
async def test_digest_generation_sort_is_stable_across_pages_and_independent_of_edits(env, db):
    seed(env, db)
    lists = importlib.import_module('app.research.services.list_queries')
    now = env.models.utcnow()
    for index in range(1, 5):
        row = add_report(env, db, index, report_type='weekly', content='' if index == 4 else '生成正文')
        row.updated_at = now + timedelta(days=10 - index)
        for version in (1, 2):
            saved = await env.repo.ResearchDao.get_report_version(db, row.id, version)
            saved.created_at = now - timedelta(days=2 if index == 1 else 1)
    add_report(env, db, 9, owner=8, report_type='weekly')
    await db.commit()
    pages = [await lists.report_page(db, user_id=7, kind='weekly', page=n, page_size=2) for n in (1, 2)]
    assert [row['id'] for page in pages for row in page['rows']] == ['1003', '1002', '1001', '1004']
    assert all(page['total'] == 4 for page in pages)
    ascending = await lists.report_page(db, user_id=7, kind='brief', sort='generated-asc')
    assert [row['id'] for row in ascending['rows']] == ['1001', '1003', '1002', '1004']
    by_title = await lists.report_page(db, user_id=7, kind='brief', sort='title-desc')
    assert [row['id'] for row in by_title['rows']] == ['1004', '1003', '1002', '1001']
    # The shared endpoint keeps its existing update-time default for research.
    research = await lists.report_page(db, user_id=7)
    assert [row['id'] for row in research['rows']] == ['1001', '1002', '1003', '1004']


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


@pytest.mark.asyncio
async def test_material_category_filter_returns_only_owner_results_without_private_classification_token(env, db):
    seed(env, db)
    categories = importlib.import_module('app.intelligence.models.categories')
    db.add(
        categories.PipelineCategory(
            id=5001, name='关键技术', prompt='技术资料', applies_to='document', is_enabled=False
        )
    )
    for index, owner in [(1001, 7), (1002, 8)]:
        db.add(
            env.material.PipelineMaterial(
                id=index,
                user_id=owner,
                name='分类资料',
                filename='资料.txt',
                storage_key=f'private/{index}',
                mime_type='text/plain',
                size=30,
                hash=f'{index:064x}',
                extracted_text='技术正文',
                status='ready',
                category_id=5001,
                classification_status='completed',
                classification_error=None,
                classification_token='private-lease-token',
            )
        )
    await db.commit()
    lists = importlib.import_module('app.research.services.list_queries')
    selected = await lists.material_page(db, user_id=7, classification='关键技术')
    assert selected['total'] == 1
    row = selected['rows'][0]
    assert row['id'] == '1001' and row['categoryId'] == '5001' and row['categoryName'] == '关键技术'
    assert row['classificationStatus'] == 'completed' and row['classificationError'] == ''
    assert not {'classificationToken', 'classification_token', 'storage_key', 'content'} & row.keys()
    unclassified = await lists.material_page(db, user_id=7, classification='未分类')
    assert unclassified['total'] == 1 and unclassified['rows'][0]['categoryId'] is None
    assert (await lists.material_page(db, user_id=7, classification='不存在的分类'))['total'] == 0


@pytest.mark.asyncio
async def test_material_duplicates_are_grouped_before_pagination_without_collapsing_edits_or_other_owners(env, db):
    seed(env, db)
    now = env.models.utcnow()

    def add(index, file_hash, *, owner=7, state='ready', edited=None, name=None):
        db.add(
            env.material.PipelineMaterial(
                id=index,
                user_id=owner,
                name=name or f'分组资料{index}',
                filename=f'{index}.txt',
                storage_key=f'private/{index}',
                mime_type='text/plain',
                size=100,
                hash=file_hash,
                extracted_text='安全摘要' * 100,
                edited_text=edited,
                status=state,
                updated_at=now + timedelta(minutes=index),
                created_at=now,
            )
        )

    # These copies would previously fall on separate raw pages.
    add(2001, 'd' * 64)
    add(2050, 'd' * 64, state='failed', name='重命名副本')
    add(2099, 'd' * 64)
    for index in range(2010, 2022):
        add(index, f'{index:064x}')
    add(2101, 'd' * 64, edited='作者修订')
    add(2102, 'd' * 64, edited='作者修订')
    add(2103, 'd' * 64, owner=8)
    add(2104, 'z' * 64)
    add(2105, 'z' * 64)
    await db.commit()
    lists = importlib.import_module('app.research.services.list_queries')
    pages = [await lists.material_page(db, user_id=7, page=n, page_size=5) for n in (1, 2, 3, 4)]
    assert [len(p['rows']) for p in pages] == [5, 5, 5, 3]
    assert all(p['total'] == 18 for p in pages)
    rows = [r for p in pages for r in p['rows']]
    assert len({r['id'] for r in rows}) == 18
    original = next(r for r in rows if r['id'] == '2001')
    assert original['duplicateIds'] == ['2001', '2050', '2099']
    assert original['status'] == '已解析' and original['isEdited'] is False
    assert {r['id'] for r in rows if r['isEdited']} == {'2101', '2102'}
    assert all(r['ownerId'] == 7 and '2103' not in r['duplicateIds'] for r in rows)
    assert all(len(r['summary']) <= 240 for r in rows)
    assert all(not {'extracted_text', 'edited_text', 'storage_key'} & r.keys() for r in rows)
    # Filtering matches any copy while deletion still names all owned copies.
    matched = await lists.material_page(db, user_id=7, keyword='重命名副本')
    assert matched['total'] == 1 and matched['rows'][0]['id'] == '2050'
    assert matched['rows'][0]['duplicateIds'] == ['2001', '2050', '2099']
    failed = await lists.material_page(db, user_id=7, status='异常')
    assert failed['total'] == 1 and failed['rows'][0]['id'] == '2050'
    other = await lists.material_page(db, user_id=8)
    assert other['total'] == 1 and other['rows'][0]['duplicateIds'] == ['2103']
