"""Dashboard reports actual totals and categories with no review workflow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.intelligence.services.dashboard import IntelligenceDashboardService


def rows(values: list[object]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = values
    result.scalars.return_value.all.return_value = values
    return result


def count(value: int) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


@pytest.mark.asyncio
async def test_dashboard_totals_merge_categories_and_preserve_collection_status() -> None:
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                rows([('安全', 4), ('检测', 2)]),
                rows([('安全', 3)]),
                rows([SimpleNamespace(source_id=1001, status='running', saved_count=5)]),
                count(12),
                count(4),
                count(8),
            ]
        )
    )
    result = await IntelligenceDashboardService.summary(db, date_formatter=str)
    assert [metric['value'] for metric in result['metrics']] == [12, 4, 8]
    assert result['hot_topics'] == [{'name': '安全', 'count': 7}, {'name': '检测', 'count': 2}]
    assert result['collect_status'] == [{'name': '1001', 'status': 'running', 'value': 5}]
    assert 'pending_reviews' not in result
    for call in db.execute.await_args_list:
        sql = str(call.args[0].compile(compile_kwargs={'literal_binds': True}))
        assert 'review_status' not in sql and 'permission_scope' not in sql
    parsed_sql = str(db.execute.await_args_list[-1].args[0].compile(compile_kwargs={'literal_binds': True}))
    assert "knowledge_files.status = 'ready'" in parsed_sql
