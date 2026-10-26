"""Retired fulltext metadata must never return through paper catalog APIs."""

from unittest.mock import AsyncMock

import pytest

from app.intelligence.models.content import PipelinePaper
from app.intelligence.repositories.content_repository import ContentDao
from app.intelligence.services.catalog import IntelligenceCatalogService


@pytest.mark.parametrize('detail', [False, True])
@pytest.mark.parametrize('abstract_zh', [None, '', '中文摘要'])
def test_paper_exposes_only_abstract_and_source_link(detail: bool, abstract_zh: str | None) -> None:
    paper = PipelinePaper(
        id=2001,
        title='论文',
        abstract='Original abstract',
        abstract_zh=abstract_zh,
        doi='10.1000/example',
        url='https://example.test/paper',
        is_pushed=False,
    )
    # Simulate an old in-memory object; retired metadata must be inert.
    paper.metadata_json = {'licensed_full_text': {'asset_key': '../backup', 'html': '<h1>FULLTEXT</h1>'}}
    row = IntelligenceCatalogService.paper_dict(paper, detail=detail, date_formatter=str)
    assert row['id'] == '2001'
    assert row['summary'] == (abstract_zh if abstract_zh is not None else 'Original abstract')
    assert row['source_url'] == 'https://example.test/paper'
    assert not {'full_text', 'full_text_url', 'body_blocks', 'metadata_json'} & row.keys()
    assert 'FULLTEXT' not in str(row)
    if detail:
        assert row['content'] == row['summary']


def test_paper_schema_has_no_fulltext_or_review_storage() -> None:
    columns = PipelinePaper.__table__.c
    assert not {
        'content',
        'content_zh',
        'metadata_json',
        'full_text',
        'full_text_url',
        'review_status',
        'permission_scope',
    } & set(columns.keys())
    assert {'abstract', 'abstract_zh', 'doi', 'url', 'published_date'} <= set(columns.keys())


@pytest.mark.asyncio
async def test_public_paper_detail_needs_no_review_and_cannot_read_backup_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = PipelinePaper(id=2002, title='论文', abstract='Only abstract', is_pushed=False)
    monkeypatch.setattr(ContentDao, 'get_article', AsyncMock(return_value=None))
    get_paper = AsyncMock(return_value=paper)
    monkeypatch.setattr(ContentDao, 'get_paper', get_paper)
    result = await IntelligenceCatalogService.get_detail(None, '2002', date_formatter=str)
    assert result['id'] == '2002'
    assert result['content'] == 'Only abstract'
    assert 'full_text' not in result and 'review_status' not in result
    get_paper.assert_awaited_once_with(None, 2002)
