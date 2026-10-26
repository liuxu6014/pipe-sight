"""BIGINT boundaries and wire references; no database or external network."""

import base64
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import BigInteger
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.business_ids import BUSINESS_ID_SEQUENCE, parse_business_id
from app.infrastructure.models.registry import register_sqlalchemy_models
from app.intelligence.api.collection_controller import BusinessId
from app.intelligence.models.collection import PipelineCrawlRun, PipelineSource
from app.intelligence.models.configuration import PipelineModelCallAudit, PipelineTemplateVersion
from app.intelligence.models.content import PipelineArticle, PipelineCategory, PipelinePaper
from app.intelligence.repositories.collection_repository import CollectionRepository
from app.intelligence.repositories.content_repository import ContentDao
from app.intelligence.services.categories import CategoryService
from app.intelligence.services.search import IntelligenceSearchService as Search
from app.intelligence.services.sources import snapshot
from exceptions.exception import ServiceException

LARGE_ID = 9007199254740993
NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


def test_production_intelligence_pk_share_sequence_and_business_fks_are_bigint():
    register_sqlalchemy_models()
    for model in (
        PipelineSource,
        PipelineCrawlRun,
        PipelineCategory,
        PipelineArticle,
        PipelinePaper,
        PipelineTemplateVersion,
        PipelineModelCallAudit,
    ):
        table = model.__table__
        assert isinstance(table.c.id.type, BigInteger)
        assert table.c.id.default is BUSINESS_ID_SEQUENCE
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "id BIGINT DEFAULT nextval('business_id_seq')" in ddl
        for column in table.columns:
            if column.foreign_keys:
                assert isinstance(column.type, BigInteger)
    assert PipelineCrawlRun.__table__.c.request_id.type.python_type is str
    assert PipelineCrawlRun.__table__.c.execution_token.type.python_type is str


@pytest.mark.parametrize(
    'invalid', ['legacy-uuid', '检测技术', '', '1.0', '１', '9223372036854775808', 0, -1, True, 1.5]
)
@pytest.mark.asyncio
async def test_invalid_entity_reference_is_rejected_before_any_query(invalid):
    db = SimpleNamespace(execute=AsyncMock(), get=AsyncMock(), rollback=AsyncMock())
    for operation in (
        CollectionRepository.source,
        CollectionRepository.run,
        CollectionRepository.locked_run,
        CollectionRepository.active,
        ContentDao.get_article,
        ContentDao.get_paper,
        CategoryService.remove,
    ):
        with pytest.raises(ValueError):
            await operation(db, invalid)
    db.execute.assert_not_awaited()
    db.get.assert_not_awaited()
    with pytest.raises(ValidationError):
        TypeAdapter(BusinessId).validate_python(invalid)


@pytest.mark.asyncio
async def test_wire_id_is_parsed_to_integer_before_lookup():
    db = SimpleNamespace(get=AsyncMock(return_value=None))
    await ContentDao.get_article(db, str(LARGE_ID))
    db.get.assert_awaited_once_with(PipelineArticle, LARGE_ID)


def test_source_snapshot_preserves_large_decimal_reference_and_opaque_config():
    config = {
        'query': '9007199254740993',
        'upstream_cursor': '123',
        'url': 'https://example.test/123',
        'retry': {'max_retries': 2},
    }
    row = SimpleNamespace(
        id=LARGE_ID, adapter='fixed', url='https://example.test', type='website', config=config, model_id=7
    )
    result = snapshot(row)
    assert result['source']['id'] == '9007199254740993'
    assert type(json.loads(json.dumps(result))['source']['id']) is str
    assert result['config'] == config and result['model_id'] == 7
    result['config']['retry']['max_retries'] = 9
    assert config['retry']['max_retries'] == 2


@pytest.mark.parametrize('filter_name', ['category_id', 'tag', 'legacy_tag', 'tags', 'directions'])
@pytest.mark.parametrize('model', [PipelineArticle, PipelinePaper])
def test_category_text_and_mixed_filters_never_bind_names_to_bigint(filter_name, model):
    values = ['检测技术', str(LARGE_ID), '完整性管理', '9223372036854775808']
    filters = {filter_name: values if filter_name in {'tags', 'directions'} else values[0]}
    statement, _, _ = ContentDao.query(model, **filters)
    compiled = statement.compile(dialect=postgresql.dialect(), compile_kwargs={'render_postcompile': True})
    for key, value in compiled.params.items():
        if key.startswith('id_'):
            assert type(value) is int and parse_business_id(value) == value
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert "'检测技术'" in sql
    assert "categories.id = '检测技术'" not in sql
    assert "categories.id IN ('" not in sql
    if filter_name in {'tags', 'directions'}:
        assert f'categories.id IN ({LARGE_ID})' in sql
        assert "'9223372036854775808'" in sql  # This can still be a category name.
    else:
        assert 'categories.id =' not in sql


@pytest.mark.parametrize('filter_name', ['tag', 'legacy_tag'])
def test_category_numeric_single_filter_uses_integer_id_and_text_name(filter_name):
    statement, _, _ = ContentDao.query(PipelineArticle, **{filter_name: str(LARGE_ID)})
    compiled = statement.compile(dialect=postgresql.dialect())
    assert LARGE_ID in compiled.params.values()
    assert str(LARGE_ID) in compiled.params.values()
    assert all(type(value) is int for key, value in compiled.params.items() if key.startswith('id_'))


def test_search_cursor_numeric_tie_break_and_wire_bigint_are_exact():
    rows = [
        {'id': str(identity), 'type': 'news', '_search_rank': 4, '_cursor_date': NOW.isoformat()}
        for identity in (9, 100, 10, LARGE_ID)
    ]
    assert [row['id'] for row in sorted(rows, key=Search._sort_key, reverse=True)] == [str(LARGE_ID), '100', '10', '9']
    context = Search._cursor_context(7, '应力', 'news', 'public', 'all', [])
    cursor = Search._encode_cursor(rows[-1], context=context)
    payload = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
    assert payload['v'] == 3 and payload['id'] == str(LARGE_ID)
    assert Search._decode_cursor(cursor, expected_context=context) == (4, NOW, 'news', LARGE_ID)
    payload['v'] = 2
    legacy = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    with pytest.raises(ServiceException):
        Search._decode_cursor(legacy, expected_context=context)


@pytest.mark.asyncio
async def test_search_merge_reuses_sql_score_date_and_numeric_cursor_predicate():
    article = SimpleNamespace(id=LARGE_ID)
    result = SimpleNamespace(all=lambda: [(article, 1, NOW)])
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    items = await ContentDao.list_articles(
        db, keyword='应力', ranked=True, search_after=(1, NOW, 'news', str(LARGE_ID))
    )
    assert items == [article] and article._search_rank == 1 and article._search_cursor_date == NOW
    statement = db.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert f'news_articles.id < {LARGE_ID}' in sql
    assert f"news_articles.id < '{LARGE_ID}'" not in sql
    row = Search._decorate_row(
        {'id': str(LARGE_ID), 'type': 'news'},
        keyword='应力',
        values=('应力', '应力', '应力', '应力'),
        cursor_date=NOW,
        sql_rank=article._search_rank,
    )
    assert Search._sort_key(row) == (1, NOW, 'news', LARGE_ID)
