"""Bounded job summaries preserve owner scope without reading manuscripts."""

import importlib
import json
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import event
from test_audit_list_pagination import add_report
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import seed

env, db, no_external_network = memory_env, memory_db, offline_network


@pytest.mark.asyncio
async def test_job_pages_are_bounded_owner_scoped_and_do_not_fetch_frozen_content(env, db):
    seed(env, db)
    for owner, indices in [(7, range(1, 24)), (8, range(30, 34))]:
        for index in indices:
            report = add_report(env, db, index, owner)
            now = env.models.utcnow() + timedelta(minutes=index)
            db.add(
                env.models.PipelineResearchJob(
                    id=2000 + index,
                    report_id=report.id,
                    request_id=f'job-page-{index}',
                    status='running' if index % 2 else 'completed',
                    progress=35 if index % 2 else 100,
                    config_snapshot={
                        'title': f'冻结标题{index:03}',
                        'type': 'research-demand',
                        'template': {'prompt': '私人冻结提示词' * 1000},
                    },
                    materials=[{'content': '完整资料禁止进入列表'}],
                    result_content='全文输出禁止进入列表' * 1000,
                    error='完整执行日志禁止进入列表',
                    created_at=now,
                    updated_at=now,
                )
            )
    await db.commit()
    queries = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        queries.append(statement)

    engine = db.s.get_bind()
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        service = importlib.import_module('app.research.services.list_queries')
        pages = [await service.job_page(db, user_id=7, page=page, page_size=10) for page in (1, 2, 3)]
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert [len(page['rows']) for page in pages] == [10, 10, 3]
    assert all(page['total'] == 23 for page in pages)
    ids = [row['id'] for page in pages for row in page['rows']]
    assert ids == [str(2000 + index) for index in range(23, 0, -1)]
    assert len(set(ids)) == 23
    for page in pages:
        for row in page['rows']:
            assert row['ownerId'] == 7 and row['jobId'] == row['id']
            assert row['title'].startswith('冻结标题') and row['type'] == 'research-demand'
            assert row['reportId'] and row['progress'] in (35, 100) and row['requiresReview'] is False
            assert (
                not {
                    'content',
                    'resultContent',
                    'config',
                    'configSnapshot',
                    'materials',
                    'selectedItems',
                    'outline',
                    'logs',
                }
                & row.keys()
            )
    assert not any(
        token in json.dumps(pages, ensure_ascii=False)
        for token in ['私人冻结提示词', '全文输出', '完整资料', '完整执行日志']
    )
    assert len(queries) == 6  # One SQL count and one limited summary read per page, no N+1 detail/history reads.
    assert all(
        'generation_tasks.result_content' not in sql and 'generation_tasks.materials' not in sql for sql in queries
    )
    assert all('report_versions' not in sql for sql in queries)
    assert all('LIMIT' in sql for sql in queries[1::2])
    other = await service.job_page(db, user_id=8)
    assert other['total'] == 4 and {row['ownerId'] for row in other['rows']} == {8}
    assert (await service.job_page(db, user_id=7))['pageSize'] == 20
    assert len((await service.job_page(db, user_id=7))['rows']) == 20
    filtered = await service.job_page(db, user_id=7, keyword='标题023', status='running')
    assert filtered['total'] == 1 and filtered['rows'][0]['id'] == '2023'
    assert (await service.job_page(db, user_id=7, keyword='标题030'))['total'] == 0
    assert (await service.job_page(db, user_id=7, keyword='%'))['total'] == 0
    assert (await service.job_page(db, user_id=7, status='active'))['total'] == 12
    assert (await service.job_page(db, user_id=7, status='completed'))['total'] == 11


def test_job_page_query_enforces_default_and_hard_cap():
    from app.research.schemas.listing import JobListQuery

    assert JobListQuery().model_dump() == {'page': 1, 'page_size': 20, 'keyword': '', 'status': ''}
    assert JobListQuery(pageNum=3, pageSize=100).page == 3
    for bad in ({'pageSize': 101}, {'pageSize': 0}, {'pageNum': 0}, {'status': 'unknown'}):
        with pytest.raises(ValidationError):
            JobListQuery(**bad)
