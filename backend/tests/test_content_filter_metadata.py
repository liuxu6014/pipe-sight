from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.intelligence.repositories.content_repository import ContentDao


@pytest.mark.asyncio
async def test_filters_use_all_catalog_metadata_without_page_limits_or_prompts() -> None:
    news = MagicMock()
    news.scalars.return_value.all.return_value = ['检测技术', '应力监测']
    papers = MagicMock()
    papers.all.return_value = [('Journal B', '2024'), ('Journal A', '2020'), (None, None)]
    categories = MagicMock()
    categories.scalars.return_value.all.return_value = ['检测技术', '应力监测', '管网安全']
    configured = MagicMock()
    configured.scalars.return_value.all.return_value = ['后台配置且尚未分类的类别']
    db = SimpleNamespace(execute=AsyncMock(side_effect=[news, papers, categories, configured]))
    result = await ContentDao.filter_options(db)
    assert result == {
        'newsTags': ['检测技术', '应力监测'],
        'journals': ['Journal A', 'Journal B'],
        'years': [2024, 2020],
        'categories': ['检测技术', '应力监测', '管网安全'],
        'articleCategories': ['后台配置且尚未分类的类别'],
    }
    for call in db.execute.await_args_list:
        sql = str(call.args[0]).upper()
        assert ' LIMIT ' not in sql and ' OFFSET ' not in sql
        assert '.PROMPT' not in sql and '.CONTENT' not in sql
