"""提交不截断；候选在 SQL 过滤、完整标题去重后再分页。"""

import re
import sys
import types
from datetime import date, datetime
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import BigInteger, Column, DateTime, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session
from test_research_simplified_20261025 import AsyncMemory, payload, raises
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_no_external_network

env = refactor_env
db = refactor_db
no_external_network = refactor_no_external_network


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['article', 'research', 'daily', 'weekly', 'monthly'])
async def test_all_generation_types_reject_overlimit_before_repository_work(env, kind):
    data = payload(report_type=kind, selected_item_ids=[str(i) for i in range(51)])
    with raises(env, '50'):
        await env.app.ResearchApplicationService.queue_job(object(), user_id=7, owner_name='用户', payload=data)


@pytest.mark.asyncio
async def test_manual_selection_does_not_drop_same_titles_or_apply_automatic_top_n(env, db, monkeypatch):
    evidence = __import__('app.research.services.evidence', fromlist=['ResearchEvidenceService'])
    articles = {
        i: NS(
            id=i,
            title='同标题',
            content='实际正文',
            content_zh=None,
            url='https://offline.invalid/' + str(i),
            source_id=601,
            published_at=datetime(2026, 10, 18),
        )
        for i in range(1, 5)
    }

    async def load(db, kind, item_id):
        return articles.get(item_id) if kind == 'article' else None

    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', load)
    rows = await evidence.ResearchEvidenceService.resolve(
        db, 7, ['1', '2', '3', '4'], payload(options={'itemCount': 1})
    )
    assert [row['id'] for row in rows] == ['1', '2', '3', '4']


def canonical_content(env, monkeypatch):
    class ContentBase(DeclarativeBase):
        pass

    class Source(ContentBase):
        __tablename__ = 'data_sources'
        id = Column(BigInteger, primary_key=True)
        type = Column(String)

    class Category(ContentBase):
        __tablename__ = 'categories'
        id = Column(BigInteger, primary_key=True)
        name = Column(String)

    class Article(ContentBase):
        __tablename__ = 'news_articles'
        id = Column(BigInteger, primary_key=True)
        source_id = Column(BigInteger)
        category_id = Column(BigInteger)
        title = Column(Text)
        published_at = Column(DateTime)
        content = Column(Text)
        content_zh = Column(Text)

    content = types.ModuleType('app.intelligence.models.content')
    content.PipelineArticle = Article
    content.PipelineCategory = Category
    content.PipelinePaper = Article
    sources = types.ModuleType('app.intelligence.models.collection')
    sources.PipelineSource = Source
    monkeypatch.setitem(sys.modules, content.__name__, content)
    monkeypatch.setitem(sys.modules, sources.__name__, sources)
    return ContentBase, Source, Category, Article


@pytest.mark.asyncio
async def test_ten_thousand_candidates_filter_and_deduplicate_before_paging(env, monkeypatch):
    base, source, category, article = canonical_content(env, monkeypatch)
    engine = create_engine('sqlite:///:memory:')

    @event.listens_for(engine, 'connect')
    def regexp(conn, _):
        conn.create_function(
            'regexp_replace', 4, lambda value, pattern, replacement, flags: re.sub(pattern, replacement, value or '')
        )

    base.metadata.create_all(engine)
    statements = []

    @event.listens_for(engine, 'before_cursor_execute')
    def trace(conn, cursor, statement, params, context, many):
        if statement.lstrip().startswith('SELECT'):
            statements.append(statement)

    session = Session(engine)
    session.add_all([source(id=601, type='website'), source(id=602, type='wechat'), category(id=801, name='检测技术')])
    rows = [
        {
            'id': i + 10000,
            'source_id': 601,
            'category_id': 801,
            'title': f'pipeline {i % 1000}!',
            'published_at': datetime(2026, 10, 18, 12),
            'content': '实际正文',
        }
        for i in range(10000)
    ]
    rows.extend(
        {
            'id': 20000 + ord(suffix),
            'source_id': 601,
            'category_id': 801,
            'title': 'pipeline ' + 'long prefix ' * 12 + suffix,
            'published_at': datetime(2026, 10, 18, 12),
            'content': '正文',
        }
        for suffix in ('A', 'B')
    )
    rows.extend(
        [
            {
                'id': 21001,
                'source_id': 602,
                'category_id': 801,
                'title': 'pipeline 公众号',
                'published_at': datetime(2026, 10, 18, 12),
                'content': '正文',
            },
            {
                'id': 21002,
                'source_id': 601,
                'category_id': 801,
                'title': 'pipeline 旧日期',
                'published_at': datetime(2026, 10, 1, 12),
                'content': '正文',
            },
        ]
    )
    session.execute(article.__table__.insert(), rows)
    session.commit()
    query = NS(
        period=[date(2026, 10, 18)],
        sources=['新闻网站'],
        directions=['检测技术'],
        keywords=['pipeline'],
        page_size=10,
        page_num=1,
    )
    try:
        first, total = await env.repo.ResearchDao.search_digest_candidates(AsyncMemory(session), query)
        query.page_num = 2
        second, second_total = await env.repo.ResearchDao.search_digest_candidates(AsyncMemory(session), query)
        assert total == second_total == 1002 and len(first) == len(second) == 10
        assert not {row.id for row in first} & {row.id for row in second}
        assert len({row.title for row in [*first, *second]}) == 20
        assert len(statements) == 4
        assert 'row_number() OVER (PARTITION BY' in statements[0] and 'LIMIT' not in statements[0]
        assert 'LIMIT' in statements[1] and 'OFFSET' in statements[1]
        assert 'review_status' not in '\n'.join(statements) and 'permission_scope' not in '\n'.join(statements)
        # 候选列表 SELECT 仅加载 id/title/published_at；正文只用于 WHERE 过滤。
        assert 'news_articles.content,' not in statements[1].split('FROM', 1)[0]
    finally:
        session.close()
        engine.dispose()
