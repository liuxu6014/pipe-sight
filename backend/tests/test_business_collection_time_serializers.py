"""Collection audit display changes must not alter operational timestamp APIs."""

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from intelligence import test_collection_rollout as support
from intelligence.test_collection_rollout import enqueue, source

env = support.env
UTC_TIME = datetime(2026, 10, 25, 16, 0, 0, 999999, tzinfo=timezone.utc)
BEIJING_TEXT = '2026-10-26 00:00:00'


@pytest.mark.asyncio
async def test_source_audit_seconds_beijing_but_next_run_remains_absolute(env: Any) -> None:
    result = await source(env, cron='0 8 * * *')
    row = await env.repo.source(env.db, result['id'])
    row.created_at = row.updated_at = UTC_TIME
    row.next_run_at = UTC_TIME
    result = env.service.source_dict(row)
    assert result['created_at'] == result['createdAt'] == BEIJING_TEXT
    assert result['updated_at'] == result['updatedAt'] == BEIJING_TEXT
    assert result['nextRunAt'] == UTC_TIME.isoformat()


@pytest.mark.asyncio
async def test_collection_run_only_audit_display_fields_change(env: Any) -> None:
    result = await source(env)
    run = await enqueue(env, result['id'])
    row = await env.repo.run(env.db, run['id'])
    row.created_at = row.updated_at = UTC_TIME
    row.available_at = UTC_TIME
    result = env.sources.run_dict(row)
    assert result['created_at'] == result['createdAt'] == BEIJING_TEXT
    assert result['updated_at'] == result['updatedAt'] == BEIJING_TEXT
    assert result['available_at'] == result['availableAt'] == UTC_TIME.isoformat()


def test_category_audit_fields_use_beijing_seconds(env: Any) -> None:
    categories = importlib.import_module('app.intelligence.services.categories')
    row = SimpleNamespace(id=999, name='类别', prompt='真实配置', is_enabled=False, model_id=None,
                           sort_order=0, applies_to='all', created_at=UTC_TIME, updated_at=UTC_TIME)
    result = categories.CategoryService.public(row)
    assert result['createdAt'] == result['updatedAt'] == BEIJING_TEXT
