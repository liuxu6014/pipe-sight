from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest import MonkeyPatch

from exceptions.exception import ServiceException
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.service.pipeline_domain_service import PipelineDomainService


class FakeDb:
    def __init__(self, source: Any = None) -> None:
        self.source = source
        self.added = []
        self.committed = False

    def add(self, item: Any) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _item: Any) -> None:
        return None


def source(**overrides: Any) -> SimpleNamespace:
    values = {
        'source_id': 'source-news',
        'source_code': 'pipe-news',
        'name': '国家管网科技资讯',
        'source_type': 'news',
        'endpoint': 'https://www.pipechina.com.cn/groupnews.html',
        'adapter_key': 'pipechina_group_news',
        'schedule_cron': '0 */2 * * *',
        'status': 'active',
        'enabled': True,
        'config_json': {'limit': 12},
        'handoff_mode': 'external',
        'processor_source_code': 'pipe-news',
        'last_run_time': None,
        'last_run_status': None,
        'success_count': 0,
        'failure_count': 0,
        'consecutive_failures': 0,
        'owner_id': 1,
        'create_time': None,
        'update_time': None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_save_source_creates_persisted_active_source(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(PipelineDao, 'get_source', AsyncMock(return_value=None))
    monkeypatch.setattr(PipelineDao, 'get_source_by_code', AsyncMock(return_value=None))
    monkeypatch.setattr(PipelineDao, 'add_source', AsyncMock(side_effect=lambda db, item: (db.add(item), item)[1]))
    db = FakeDb()

    result = await PipelineDomainService.save_source(
        db,
        source_id=None,
        source_code='pipe-news-new',
        name='新增资讯源',
        source_type='news',
        endpoint='https://example.com/news',
        adapter_key='pipechina_group_news',
        schedule_cron='0 */4 * * *',
        enabled=True,
        config_json={'limit': 10},
        handoff_mode='local',
        processor_source_code='pipe-news-new',
        owner_id=7,
    )

    assert result['source_code'] == 'pipe-news-new'
    assert result['status'] == 'enabled'
    assert db.added[0].status == 'active'
    assert db.added[0].enabled is True
    assert db.committed is True


@pytest.mark.asyncio
async def test_save_source_rejects_unknown_adapter(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(PipelineDao, 'get_source', AsyncMock(return_value=None))
    monkeypatch.setattr(PipelineDao, 'get_source_by_code', AsyncMock(return_value=None))

    with pytest.raises(ServiceException) as exc_info:
        await PipelineDomainService.save_source(
            FakeDb(),
            source_id=None,
            source_code='pipe-news-new',
            name='新增资讯源',
            source_type='news',
            endpoint='https://example.com/news',
            adapter_key='unknown-adapter',
            schedule_cron='',
            enabled=True,
            config_json={},
            handoff_mode='local',
            processor_source_code='',
            owner_id=7,
        )
    assert '适配器' in exc_info.value.message


@pytest.mark.asyncio
async def test_toggle_source_updates_enabled_and_status(monkeypatch: MonkeyPatch) -> None:
    item = source()
    monkeypatch.setattr(PipelineDao, 'get_source', AsyncMock(return_value=item))
    db = FakeDb(item)

    result = await PipelineDomainService.set_source_enabled(db, 'source-news', False)

    assert result['status'] == 'disabled'
    assert item.enabled is False
    assert item.status == 'inactive'
    assert db.committed is True
