from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers

from app.infrastructure.models.registry import register_sqlalchemy_models
from app.intelligence.repositories.content_repository import ContentDao
from app.intelligence.services.catalog import IntelligenceCatalogService
from app.intelligence.services.categories import CategoryService
from app.library.models.materials import PipelineMaterial
from app.schema_contract import load_contract
from config import get_db
from config.database import Base
from exceptions.exception import ServiceException


def test_registered_models_match_approved_columns_without_retired_tables():
    register_sqlalchemy_models()
    configure_mappers()
    contract = load_contract()
    for table in contract['tables']:
        if table['name'] in {'alembic_version', 'apscheduler_jobs'}:
            continue
        assert set(Base.metadata.tables[table['name']].columns.keys()) == {col['name'] for col in table['columns']}
    assert not {'content_review_events', 'prompt_versions', 'model_routes', 'template_versions'} & set(
        Base.metadata.tables
    )


def test_startup_refuses_schema_mismatch_without_creating_tables(monkeypatch):
    inspector = SimpleNamespace(has_table=lambda *args, **kwargs: False)
    monkeypatch.setattr(get_db, 'inspect', lambda connection: inspector)
    with pytest.raises(RuntimeError, match='备份和迁移'):
        get_db.validate_schema(object())


def test_news_display_is_source_derived_and_has_no_review_gate():
    row = SimpleNamespace(
        id=1001,
        source=SimpleNamespace(name='某公众号', type='wechat'),
        category=None,
        category_id=None,
        content='原文',
        content_zh=None,
        title='标题',
        published_at=None,
        url='https://example.test/a',
        author=None,
        is_pushed=False,
    )
    result = IntelligenceCatalogService.article_dict(row, detail=True, date_formatter=lambda v: '')
    assert result['source_type'] == 'wechat'
    assert result['content'] == '原文'
    assert not {'status', 'processing_status', 'review_status'} & result.keys()


def test_paper_keeps_year_precision_and_only_abstract():
    row = SimpleNamespace(
        id=2001,
        category=None,
        category_id=None,
        source=None,
        abstract='abstract',
        abstract_zh=None,
        published_date='2024',
        journal='J',
        title='T',
        title_zh=None,
        url=None,
        doi='10.1/example',
        authors='One; Two',
        is_pushed=False,
    )
    result = IntelligenceCatalogService.paper_dict(row, detail=True, date_formatter=lambda v: '')
    assert result['publish_time'] == '2024'
    assert result['authors'] == ['One', 'Two']
    assert result['content'] == 'abstract'
    assert 'full_text' not in result


def test_search_uses_all_content_and_owner_scope_in_sql():
    query, _, _ = ContentDao.query(PipelineMaterial, user_id=7, keyword='100%_test')
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert 'knowledge_files.user_id =' in sql
    assert 'coalesce(knowledge_files.edited_text, knowledge_files.extracted_text)' in sql
    assert 'LIMIT' not in sql
    compiled = query.compile(dialect=postgresql.dialect())
    assert '%100\\%\\_test%' in compiled.params.values()


@pytest.mark.asyncio
async def test_classification_never_silently_takes_first_of_multiple_categories():
    categories = [SimpleNamespace(id=n, name=str(n), model_id=1, prompt='规则') for n in (1, 2)]
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: categories))
    model = SimpleNamespace(
        id=1,
        provider='openai',
        code='text',
        base_url='https://example.test',
        parameters={},
        is_enabled=True,
        capabilities=['text_generate'],
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=result), get=AsyncMock(return_value=model))
    call = AsyncMock(return_value='{"match":true}')
    with pytest.raises(ServiceException) as caught:
        await CategoryService.classify(db, title='文章', content='正文', kind='news', gateway=call)
    assert '多个类别' in caught.value.message
    assert call.await_count == 2


@pytest.mark.asyncio
async def test_classification_requires_actual_boolean_not_truthy_string():
    category = SimpleNamespace(id=501, name='C', model_id=1, prompt='规则')
    model = SimpleNamespace(
        id=1,
        provider='openai',
        code='text',
        base_url='https://example.test',
        parameters={},
        is_enabled=True,
        capabilities=['text_generate'],
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [category]))),
        get=AsyncMock(return_value=model),
    )
    with pytest.raises(ServiceException) as caught:
        await CategoryService.classify(
            db, title='文章', content='正文', kind='news', gateway=AsyncMock(return_value='{"match":"false"}')
        )
    assert '格式错误' in caught.value.message
