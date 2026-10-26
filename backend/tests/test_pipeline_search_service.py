import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import sqlite

from app.intelligence.api.controller import search_research_materials
from app.intelligence.repositories.content_repository import ContentDao
from app.intelligence.services.application import IntelligenceApplicationService
from app.intelligence.services.search import IntelligenceSearchService
from app.library.models.materials import PipelineMaterial
from app.research.models.research_models import PipelineReport
from exceptions.exception import ServiceException

PUBLIC_TOTAL = 12
INTERNAL_TOTAL = 5
NEWS_TOTAL = 3
EVIDENCE_TOTAL = 15
RESEARCH_USER_ID = 42


@pytest.mark.parametrize('parse_status', ['queued', 'parsing', 'failed', 'indexed'])
def test_material_search_preserves_parse_state(parse_status: str) -> None:
    material = SimpleNamespace(
        id='3001',
        name='test.txt',
        edited_text=None,
        extracted_text='',
        updated_at=datetime(2026, 10, 18),
        status=parse_status,
    )
    row = IntelligenceSearchService._material_row(material, _date)
    assert row['parseStatus'] == parse_status


@pytest.mark.asyncio
async def test_research_evidence_search_excludes_reports_and_preserves_global_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    articles = AsyncMock(return_value=[_article('1001', datetime(2026, 10, 2))])
    papers = AsyncMock(return_value=[_paper('2001')])
    documents = AsyncMock(return_value=[])
    reports = AsyncMock(return_value=[])
    monkeypatch.setattr(ContentDao, 'list_articles', articles)
    monkeypatch.setattr(ContentDao, 'list_papers', papers)
    monkeypatch.setattr(ContentDao, 'list_search_materials', documents)
    monkeypatch.setattr(ContentDao, 'list_search_reports', reports)
    monkeypatch.setattr(ContentDao, 'count_articles', AsyncMock(return_value=8))
    monkeypatch.setattr(ContentDao, 'count_papers', AsyncMock(return_value=4))
    monkeypatch.setattr(ContentDao, 'count_search_materials', AsyncMock(return_value=3))
    report_count = AsyncMock(return_value=99)
    monkeypatch.setattr(ContentDao, 'count_search_reports', report_count)
    result = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=42,
        keyword='管网',
        content_type='evidence',
        source='all',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=10,
        date_formatter=_date,
        max_page_num=None,
    )
    assert result['total'] == EVIDENCE_TOTAL
    assert {row['type'] for row in result['rows']} == {'news', 'paper'}
    reports.assert_not_awaited()
    report_count.assert_not_awaited()
    assert documents.await_args.args[1] == RESEARCH_USER_ID
    assert documents.await_args.kwargs['keyword'] == '管网'
    assert articles.await_args.kwargs['keyword'] == '管网'
    assert papers.await_args.kwargs['keyword'] == '管网'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('kind', 'expected_type', 'source'),
    [
        ('all', 'evidence', 'all'),
        ('news', 'website', 'public'),
        ('wechat', 'wechat', 'public'),
        ('paper', 'paper', 'public'),
        ('document', 'document', 'internal'),
    ],
)
async def test_research_material_endpoint_passes_authenticated_scope_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    expected_type: str,
    source: str,
) -> None:
    search = AsyncMock(return_value={'rows': [], 'total': 0})
    monkeypatch.setattr(IntelligenceApplicationService, 'search_intelligence', search)
    await search_research_materials(
        request=SimpleNamespace(),
        query_db=SimpleNamespace(),
        current_user=SimpleNamespace(user=SimpleNamespace(user_id=42)),
        keyword='应力',
        content_type=kind,
        page_num=101,
        page_size=20,
    )
    assert search.await_args.kwargs == {
        'user_id': 42,
        'keyword': '应力',
        'content_type': expected_type,
        'source': source,
        'date_range': 'all',
        'directions': None,
        'page_num': 101,
        'page_size': 20,
        'max_page_num': None,
    }


MAX_SNIPPET_WITH_CONTEXT = 242
MAX_SNIPPET_WITH_ELLIPSIS = 241


@pytest.mark.asyncio
@pytest.mark.parametrize(('kind', 'article_type'), [('website', 'news'), ('wechat', 'wechat')])
async def test_research_article_tabs_filter_rows_and_total_by_source_type(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    article_type: str,
) -> None:
    row = _article('1101', datetime(2026, 10, 2))
    row.source.type = 'website' if article_type == 'news' else article_type
    articles = AsyncMock(return_value=[row])
    count = AsyncMock(return_value=NEWS_TOTAL)
    monkeypatch.setattr(ContentDao, 'list_articles', articles)
    monkeypatch.setattr(ContentDao, 'count_articles', count)
    monkeypatch.setattr(ContentDao, 'count_papers', AsyncMock(return_value=0))
    result = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=42,
        keyword='管道',
        content_type=kind,
        source='public',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=10,
        date_formatter=_date,
        max_page_num=None,
    )
    assert result['total'] == NEWS_TOTAL
    assert result['rows'][0]['source_type'] == article_type
    assert articles.await_args.kwargs['article_type'] == article_type
    assert count.await_args.kwargs['article_type'] == article_type


def test_highlight_parts_returns_plain_text_segments() -> None:
    assert IntelligenceSearchService._highlight_parts('应力监测与腐蚀防护', '应力') == [
        {'text': '应力', 'match': True},
        {'text': '监测与腐蚀防护', 'match': False},
    ]


def test_snippet_parts_prefers_matching_body_and_limits_context() -> None:
    parts = IntelligenceSearchService._snippet_parts(
        '这是没有命中词的摘要。',
        '前置说明。' * 80 + '应力监测' + '后续说明。' * 80,
        '应力监测',
    )
    text = ''.join(part['text'] for part in parts)
    assert '应力监测' in text
    assert len(text) <= MAX_SNIPPET_WITH_CONTEXT
    assert any(part['match'] and part['text'] == '应力监测' for part in parts)


def test_snippet_parts_truncates_summary_without_keyword() -> None:
    parts = IntelligenceSearchService._snippet_parts('摘要。' * 100, None, None)
    text = ''.join(part['text'] for part in parts)
    assert text.endswith('…')
    assert len(text) <= MAX_SNIPPET_WITH_ELLIPSIS
    assert IntelligenceSearchService._highlight_parts('<b>应力</b>', '应力') == [
        {'text': '<b>', 'match': False},
        {'text': '应力', 'match': True},
        {'text': '</b>', 'match': False},
    ]


def _date(value: datetime | None) -> str:
    return value.strftime('%Y-%m-%d') if value else ''


def _article(article_id: str, published_time: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        id=int(article_id),
        title=f'资讯 {article_id}',
        source=SimpleNamespace(type='website', name='公开来源'),
        category=SimpleNamespace(name='检测技术'),
        category_id=501,
        published_at=published_time,
        content='资讯摘要',
        content_zh=None,
        author=None,
        url='https://example.test/news',
        is_pushed=False,
    )


def _paper(paper_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=int(paper_id),
        title=f'论文 {paper_id}',
        title_zh=None,
        source=SimpleNamespace(name='论文数据库'),
        journal='Journal',
        published_date='2026-10-02',
        created_at=datetime(2026, 10, 18),
        category=SimpleNamespace(name='完整性管理'),
        category_id=502,
        abstract='论文摘要',
        abstract_zh=None,
        url='https://example.test/paper',
        doi='10.1000/example',
        authors='',
        is_pushed=False,
    )


@pytest.mark.asyncio
async def test_search_merges_public_rows_and_keeps_candidate_reads_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_articles = AsyncMock(
        return_value=[
            _article('1001', datetime(2026, 10, 2)),
            _article('1002', datetime(2026, 10, 1)),
        ]
    )
    list_papers = AsyncMock(return_value=[_paper('2001')])
    monkeypatch.setattr(ContentDao, 'list_articles', list_articles)
    monkeypatch.setattr(ContentDao, 'count_articles', AsyncMock(return_value=8))
    monkeypatch.setattr(ContentDao, 'list_papers', list_papers)
    monkeypatch.setattr(ContentDao, 'count_papers', AsyncMock(return_value=4))

    result = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=7,
        keyword='管网',
        content_type='all',
        source='public',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=3,
        date_formatter=_date,
    )

    assert result['total'] == PUBLIC_TOTAL
    assert [row['id'] for row in result['rows']] == ['2001', '1001', '1002']
    list_articles.assert_awaited_once_with(
        SimpleNamespace(),
        ranked=True,
        keyword='管网',
        published_from=None,
        published_to=None,
        directions=[],
        offset=0,
        limit=3,
    )
    list_papers.assert_awaited_once_with(
        SimpleNamespace(),
        ranked=True,
        keyword='管网',
        published_from=None,
        published_to=None,
        directions=[],
        offset=0,
        limit=3,
    )
    assert result['counts'] == {'news': 8, 'paper': 4, 'document': 0, 'report': 0, 'all': 12}


@pytest.mark.asyncio
async def test_search_uses_stable_tiebreakers_when_publish_times_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    same_time = datetime(2026, 10, 2, 9, 30)
    monkeypatch.setattr(
        ContentDao,
        'list_articles',
        AsyncMock(return_value=[_article('9', same_time), _article('10', same_time)]),
    )
    monkeypatch.setattr(ContentDao, 'count_articles', AsyncMock(return_value=2))
    monkeypatch.setattr(ContentDao, 'count_papers', AsyncMock(return_value=0))

    result = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=7,
        keyword=None,
        content_type='news',
        source='public',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=20,
        date_formatter=_date,
    )

    assert [row['id'] for row in result['rows']] == ['10', '9']


@pytest.mark.asyncio
async def test_search_prioritizes_title_matches_before_summary_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    same_time = datetime(2026, 10, 2, 9, 30)
    title_match = _article('1201', same_time)
    title_match.title = '应力监测专题'
    summary_match = _article('1202', same_time)
    summary_match.content = '正文提到应力监测，但标题不包含关键词'
    monkeypatch.setattr(ContentDao, 'list_articles', AsyncMock(return_value=[summary_match, title_match]))
    monkeypatch.setattr(ContentDao, 'count_articles', AsyncMock(return_value=2))
    monkeypatch.setattr(ContentDao, 'count_papers', AsyncMock(return_value=0))

    result = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=7,
        keyword='应力监测',
        content_type='news',
        source='public',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=20,
        date_formatter=_date,
    )

    assert [row['id'] for row in result['rows']] == ['1201', '1202']


@pytest.mark.asyncio
async def test_search_returns_counts_for_inactive_tabs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ContentDao,
        'list_articles',
        AsyncMock(return_value=[_article('1001', datetime(2026, 10, 2))]),
    )
    monkeypatch.setattr(ContentDao, 'count_articles', AsyncMock(return_value=3))
    monkeypatch.setattr(ContentDao, 'count_papers', AsyncMock(return_value=4))
    monkeypatch.setattr(ContentDao, 'count_search_materials', AsyncMock(return_value=5))
    monkeypatch.setattr(ContentDao, 'count_search_reports', AsyncMock(return_value=6))

    result = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=7,
        keyword=None,
        content_type='news',
        source='all',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=20,
        date_formatter=_date,
    )

    assert result['total'] == NEWS_TOTAL
    assert result['counts'] == {'news': 3, 'paper': 4, 'document': 5, 'report': 6, 'all': 18}


@pytest.mark.asyncio
async def test_search_uses_source_publication_window_for_papers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_papers = AsyncMock(return_value=[_paper('2001')])
    count_papers = AsyncMock(return_value=1)
    monkeypatch.setattr(ContentDao, 'list_papers', list_papers)
    monkeypatch.setattr(ContentDao, 'count_papers', count_papers)
    monkeypatch.setattr(ContentDao, 'count_articles', AsyncMock(return_value=0))

    await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=7,
        keyword=None,
        content_type='paper',
        source='public',
        date_range='week',
        directions=None,
        page_num=1,
        page_size=20,
        date_formatter=_date,
    )

    list_call = list_papers.await_args.kwargs
    count_call = count_papers.await_args.kwargs
    assert list_call['published_to'] - list_call['published_from'] == timedelta(days=7)
    assert count_call['published_to'] - count_call['published_from'] == timedelta(days=7)
    assert 'year_from' not in list_call
    assert 'year_to' not in list_call


@pytest.mark.asyncio
async def test_search_passes_user_scope_to_internal_material_and_report_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    material = SimpleNamespace(
        id='3002',
        name='内部资料',
        edited_text=None,
        extracted_text='资料摘要',
        status='ready',
        updated_at=datetime(2026, 10, 2),
    )
    report = SimpleNamespace(
        id='4001',
        type='research',
        title='我的报告',
        version=1,
        content='报告正文',
        updated_at=datetime(2026, 10, 2),
    )
    list_materials = AsyncMock(return_value=[material])
    count_materials = AsyncMock(return_value=3)
    list_reports = AsyncMock(return_value=[report])
    count_reports = AsyncMock(return_value=2)
    monkeypatch.setattr(ContentDao, 'list_search_materials', list_materials)
    monkeypatch.setattr(ContentDao, 'count_search_materials', count_materials)
    monkeypatch.setattr(ContentDao, 'list_search_reports', list_reports)
    monkeypatch.setattr(ContentDao, 'count_search_reports', count_reports)

    result = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=42,
        keyword='资料',
        content_type='all',
        source='internal',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=10,
        date_formatter=_date,
    )

    assert result['total'] == INTERNAL_TOTAL
    assert {row['type'] for row in result['rows']} == {'document', 'report'}
    list_materials.assert_awaited_once_with(
        SimpleNamespace(),
        42,
        ranked=True,
        keyword='资料',
        updated_from=None,
        updated_to=None,
        directions=[],
        offset=0,
        limit=10,
    )
    count_materials.assert_awaited_once_with(
        SimpleNamespace(),
        42,
        keyword='资料',
        updated_from=None,
        updated_to=None,
        directions=[],
    )
    list_reports.assert_awaited_once_with(
        SimpleNamespace(),
        42,
        ranked=True,
        keyword='资料',
        updated_from=None,
        updated_to=None,
        directions=[],
        offset=0,
        limit=10,
    )
    count_reports.assert_awaited_once_with(
        SimpleNamespace(),
        42,
        keyword='资料',
        updated_from=None,
        updated_to=None,
        directions=[],
    )


@pytest.mark.asyncio
async def test_search_rejects_unknown_filters() -> None:
    with pytest.raises(ServiceException):
        await IntelligenceSearchService.search(
            SimpleNamespace(),
            user_id=1,
            keyword=None,
            content_type='video',
            source='all',
            date_range='all',
            directions=None,
            page_num=1,
            page_size=10,
            date_formatter=_date,
        )

    with pytest.raises(ServiceException):
        await IntelligenceSearchService.search(
            SimpleNamespace(),
            user_id=1,
            keyword=None,
            content_type='all',
            source='private',
            date_range='all',
            directions=None,
            page_num=1,
            page_size=10,
            date_formatter=_date,
        )


@pytest.mark.asyncio
async def test_search_rejects_unknown_date_range() -> None:
    with pytest.raises(ServiceException):
        await IntelligenceSearchService.search(
            SimpleNamespace(),
            user_id=1,
            keyword=None,
            content_type='all',
            source='all',
            date_range='month',
            directions=None,
            page_num=1,
            page_size=10,
            date_formatter=_date,
        )


@pytest.mark.asyncio
async def test_search_rejects_unbounded_deep_page_requests() -> None:
    with pytest.raises(ServiceException) as exc_info:
        await IntelligenceSearchService.search(
            SimpleNamespace(),
            user_id=1,
            keyword=None,
            content_type='all',
            source='all',
            date_range='all',
            directions=None,
            page_num=101,
            page_size=100,
            date_formatter=_date,
        )
    assert exc_info.value.message == '搜索页码不能超过100页，请缩小筛选范围'


@pytest.mark.asyncio
async def test_search_rejects_invalid_cursor() -> None:
    with pytest.raises(ServiceException) as exc_info:
        await IntelligenceSearchService.search(
            SimpleNamespace(),
            user_id=1,
            keyword='应力监测',
            content_type='news',
            source='public',
            date_range='all',
            directions=None,
            page_num=1,
            page_size=10,
            date_formatter=_date,
            cursor='not-a-valid-cursor',
        )
    assert exc_info.value.message == '搜索游标无效，请重新搜索'


@pytest.mark.asyncio
async def test_search_returns_and_consumes_a_stable_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _article('1001', datetime(2026, 10, 2, 9, 31))
    first.title = '应力监测专题 A'
    second = _article('1002', datetime(2026, 10, 2, 9, 30))
    second.title = '应力监测专题 B'
    list_articles = AsyncMock(return_value=[first, second])
    monkeypatch.setattr(ContentDao, 'list_articles', list_articles)
    monkeypatch.setattr(ContentDao, 'count_articles', AsyncMock(return_value=2))
    monkeypatch.setattr(ContentDao, 'count_papers', AsyncMock(return_value=0))

    first_page = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=7,
        keyword='应力监测',
        content_type='news',
        source='public',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=1,
        date_formatter=_date,
    )

    assert first_page['next_cursor']
    assert [row['id'] for row in first_page['rows']] == ['1001']

    list_articles.reset_mock()
    list_articles.return_value = [second]
    second_page = await IntelligenceSearchService.search(
        SimpleNamespace(),
        user_id=7,
        keyword='应力监测',
        content_type='news',
        source='public',
        date_range='all',
        directions=None,
        page_num=2,
        page_size=1,
        date_formatter=_date,
        cursor=first_page['next_cursor'],
    )

    assert [row['id'] for row in second_page['rows']] == ['1002']
    assert second_page['next_cursor'] is None
    assert list_articles.await_args.kwargs['limit'] == len(first_page['rows']) + 1
    assert list_articles.await_args.kwargs['search_after'] == (
        4,
        datetime(2026, 10, 2, 9, 31, tzinfo=timezone.utc),
        'news',
        1001,
    )

    with pytest.raises(ServiceException) as exc_info:
        await IntelligenceSearchService.search(
            SimpleNamespace(),
            user_id=7,
            keyword='腐蚀防护',
            content_type='news',
            source='public',
            date_range='all',
            directions=None,
            page_num=2,
            page_size=1,
            date_formatter=_date,
            cursor=first_page['next_cursor'],
        )
    assert exc_info.value.message == '搜索游标无效，请重新搜索'


@pytest.mark.asyncio
async def test_internal_search_counts_use_the_same_search_expression_as_lists() -> None:
    class _CountResult:
        def scalar_one(self) -> int:
            return 0

    db = SimpleNamespace(execute=AsyncMock(return_value=_CountResult()))

    await ContentDao.count_search_materials(db, 7, keyword='管网')
    materials_sql = str(db.execute.await_args.args[0].compile(compile_kwargs={'literal_binds': True}))
    assert 'knowledge_files.name' in materials_sql
    assert 'knowledge_files.user_id = 7' in materials_sql
    assert 'coalesce(knowledge_files.edited_text, knowledge_files.extracted_text)' in materials_sql

    await ContentDao.count_search_reports(db, 7, keyword='管网')
    reports_sql = str(db.execute.await_args.args[0].compile(compile_kwargs={'literal_binds': True}))
    assert 'reports.title' in reports_sql
    assert 'reports.user_id = 7' in reports_sql
    assert 'reports.content' in reports_sql


@pytest.mark.parametrize('model', [PipelineMaterial, PipelineReport])
def test_internal_query_cannot_return_another_users_matching_content(
    model: type[PipelineMaterial] | type[PipelineReport],
) -> None:
    query, _, _ = ContentDao.query(model, user_id=42, keyword='管网')
    query = query.with_only_columns(model.id, maintain_column_froms=True)
    compiled = query.compile(dialect=sqlite.dialect())
    with sqlite3.connect(':memory:') as db:
        if model is PipelineMaterial:
            db.execute(
                'CREATE TABLE knowledge_files (id TEXT, user_id INTEGER, name TEXT, edited_text TEXT, extracted_text TEXT)'
            )
            db.executemany(
                'INSERT INTO knowledge_files VALUES (?, ?, ?, ?, ?)',
                [
                    ('mine', 42, '资料', None, '管网原文'),
                    ('other', 99, '管网资料', None, '管网原文'),
                    ('cleared', 42, '资料', '', '管网原文'),
                    ('edited', 42, '资料', '其他正文', '管网原文'),
                ],
            )
        else:
            db.execute('CREATE TABLE reports (id TEXT, user_id INTEGER, title TEXT, content TEXT)')
            db.executemany(
                'INSERT INTO reports VALUES (?, ?, ?, ?)',
                [
                    ('mine', 42, '报告', '管网正文'),
                    ('other', 99, '管网报告', '管网正文'),
                ],
            )
        params = tuple(compiled.params[name] for name in compiled.positiontup)
        assert db.execute(str(compiled), params).fetchall() == [('mine',)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'changed',
    [
        {'user_id': 99},
        {'source': 'all'},
        {'content_type': 'paper'},
        {'date_range': 'week'},
        {'directions': '检测技术'},
    ],
)
async def test_cursor_cannot_be_reused_for_another_user_or_filter(changed: dict[str, str | int]) -> None:
    params = {
        'user_id': 42,
        'keyword': '管网',
        'content_type': 'news',
        'source': 'public',
        'date_range': 'all',
        'directions': None,
    }
    context = IntelligenceSearchService._cursor_context(42, '管网', 'news', 'public', 'all', [])
    cursor = IntelligenceSearchService._encode_cursor(
        {'id': '1001', 'type': 'news', '_search_rank': 4, '_cursor_date': '2026-10-02T00:00:00+00:00'},
        context=context,
    )
    with pytest.raises(ServiceException) as error:
        await IntelligenceSearchService.search(
            None,
            **(params | changed),
            page_num=1,
            page_size=10,
            date_formatter=_date,
            cursor=cursor,
        )
    assert error.value.message == '搜索游标无效，请重新搜索'
