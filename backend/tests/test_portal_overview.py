"""Portal counters execute aggregate SELECTs against readable/owned records only."""

import json
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy.dialects import sqlite

from app.intelligence.api import controller
from app.intelligence.services.application import IntelligenceApplicationService
from app.intelligence.services.catalog import IntelligenceCatalogService
from config.get_db import get_db
from exceptions.exception import AuthException


class SelectOnlyDB:
    """Supply rows as CTEs: no tables, schema changes or data writes, even in tests."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def execute(self, query: Any) -> Any:
        sql = str(query.compile(dialect=sqlite.dialect(), compile_kwargs={'literal_binds': True}))
        self.queries.append(sql)
        assert sql.startswith('SELECT') and 'count(' in sql.lower()
        fixtures = """WITH
        data_sources(id,type) AS (VALUES ('s','website'),('w','wechat')),
        news_articles(created_at,source_id) AS (VALUES
          ('2026-10-14 23:59:59.999999','s'),
          ('2026-10-15 00:00:00.000000','w'),
          ('2026-10-15 23:59:59.999999','s'),
          ('2026-10-16 00:00:00.000000','s'),
          ('2026-10-15 12:00:00.000000','s'),
          ('2026-10-15 12:00:00.000000','s'),
          ('2026-10-15 12:00:00.000000','w')),
        papers(created_at) AS (VALUES
          ('2026-10-15 00:00:00.000000'),
          ('2026-10-14 23:59:59.999999'),
          ('2026-10-15 12:00:00.000000'),
          ('2026-10-15 12:00:00.000000')),
        reports(user_id) AS (VALUES (7),(7),(8),(8),(1))
        """
        with sqlite3.connect(':memory:') as connection:
            connection.row_factory = sqlite3.Row
            row = dict(connection.execute(fixtures + sql).fetchone())
        return SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: row))


@pytest.mark.asyncio
@pytest.mark.parametrize(('user_id', 'report_count'), [(7, 2), (8, 2), (1, 1), (99, 0)])
async def test_overview_uses_readable_catalog_current_owner_and_shanghai_half_open_day(
    user_id: int,
    report_count: int,
) -> None:
    db = SelectOnlyDB()
    result = await IntelligenceCatalogService.portal_overview(
        db,
        user_id=user_id,
        now=datetime(2026, 10, 14, 16, 5, tzinfo=timezone.utc),
    )
    assert result == {
        'paperCount': 4,
        'newsCount': 5,
        'wechatCount': 2,
        'todayPaperCount': 3,
        'todayNewsCount': 3,
        'todayWechatCount': 2,
        'todayAddedCount': 8,
        'reportCount': report_count,
        'todayDate': '2026-10-15',
    }
    assert len(db.queries) == 1
    assert 'published_time' not in db.queries[0] and 'published_at' not in db.queries[0]
    assert '2026-10-15 00:00:00' in db.queries[0] and '2026-10-16 00:00:00' in db.queries[0]


@pytest.mark.asyncio
async def test_empty_catalog_counters_are_zero() -> None:
    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                mappings=lambda: SimpleNamespace(
                    one=lambda: {
                        'paper_count': 0,
                        'news_count': 0,
                        'wechat_count': 0,
                        'today_paper_count': 0,
                        'today_news_count': 0,
                        'today_wechat_count': 0,
                        'today_added_count': 0,
                        'report_count': 0,
                    }
                ),
            )
        )
    )
    result = await IntelligenceCatalogService.portal_overview(
        db,
        user_id=7,
        now=datetime(2026, 10, 15, 12, tzinfo=timezone.utc),
    )
    assert all(
        result[key] == 0
        for key in [
            'paperCount',
            'newsCount',
            'wechatCount',
            'todayPaperCount',
            'todayNewsCount',
            'todayWechatCount',
            'todayAddedCount',
            'reportCount',
        ]
    )


@pytest.mark.asyncio
async def test_overview_route_requires_login_and_passes_current_user_even_for_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = next(r for r in controller.controller.routes if r.path == '/pipeline/portal/overview')
    assert any(type(d.dependency).__name__ == 'PreAuth' for d in route.dependencies)
    assert any(d.name == 'current_user' for d in route.dependant.dependencies)
    assert not any(getattr(d.dependency, 'role_key', None) for d in route.dependencies)
    overview = AsyncMock(
        return_value={
            'paperCount': 2,
            'newsCount': 4,
            'todayAddedCount': 3,
            'reportCount': 1,
            'todayDate': '2026-10-15',
        }
    )
    monkeypatch.setattr(IntelligenceApplicationService, 'portal_overview', overview)
    db = object()
    response = await route.endpoint(
        request=None, query_db=db, current_user=SimpleNamespace(user=SimpleNamespace(user_id=1), is_admin=True)
    )
    overview.assert_awaited_once_with(db, user_id=1)
    assert json.loads(response.body)['data']['reportCount'] == 1


def test_overview_without_login_is_rejected_before_any_catalog_read(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(controller.controller)
    app.dependency_overrides[get_db] = lambda: None
    app.add_exception_handler(
        AuthException, lambda _request, _error: JSONResponse({'detail': 'login required'}, status_code=401)
    )
    overview = AsyncMock()
    monkeypatch.setattr(IntelligenceApplicationService, 'portal_overview', overview)
    with TestClient(app) as client:
        response = client.get('/pipeline/portal/overview?user_id=8&include_all=true')
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    overview.assert_not_awaited()
