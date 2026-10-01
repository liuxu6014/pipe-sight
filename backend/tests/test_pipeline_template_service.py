from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from exceptions.exception import ServiceException
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.service.pipeline_template_service import PipelineTemplateService


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.committed = False

    def add(self, item: object) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _item: object) -> None:
        return None


def payload(**overrides: object) -> dict:
    value = {
        'code': 'R-99',
        'category': 'research',
        'report_type': 'research-demand',
        'name': '测试模板',
        'description': '测试用途',
        'color': '#2764e7',
        'version_label': 'V1.0',
        'formats': ['docx'],
        'sections': [{'id': 1, 'title': '问题分析', 'words': 1000, 'required': True}],
    }
    value.update(overrides)
    return value


def template(**overrides: object) -> SimpleNamespace:
    value = {
        'template_id': 'template-1',
        'template_key': 'research-test',
        'code': 'R-99',
        'category': 'research',
        'report_type': 'research-demand',
        'name': '测试模板',
        'description': '测试用途',
        'color': '#2764e7',
        'version_label': 'V1.0',
        'version_no': 1,
        'status': 'draft',
        'formats': ['docx'],
        'sections': [{'id': 1, 'title': '问题分析'}],
        'usage_count': 0,
        'operator_name': '管理员',
        'published_at': None,
        'update_time': None,
    }
    value.update(overrides)
    return SimpleNamespace(**value)


@pytest.mark.asyncio
async def test_save_template_creates_new_draft_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PipelineDao, 'get_latest_template', AsyncMock(return_value=None))
    monkeypatch.setattr(PipelineDao, 'add_template', AsyncMock(side_effect=lambda db, item: (db.add(item), item)[1]))
    db = FakeDb()

    result = await PipelineTemplateService.save_draft(
        db,
        template_key='research-test',
        payload=payload(),
        operator_id=1,
        operator_name='管理员',
    )

    assert result['templateKey'] == 'research-test'
    assert result['status'] == 'draft'
    assert db.added[0].version_no == 1
    assert db.committed is True


@pytest.mark.asyncio
async def test_publish_template_retires_previous_version(monkeypatch: pytest.MonkeyPatch) -> None:
    latest = template(version_no=2, status='draft')
    previous = template(template_id='template-0', version_no=1, status='published')
    monkeypatch.setattr(PipelineDao, 'get_latest_template', AsyncMock(return_value=latest))
    monkeypatch.setattr(PipelineDao, 'list_template_versions', AsyncMock(return_value=[latest, previous]))
    db = FakeDb()

    result = await PipelineTemplateService.publish(db, 'research-test', operator_id=1, operator_name='管理员')

    assert result['status'] == 'published'
    assert latest.status == 'published'
    assert previous.status == 'retired'
    assert db.committed is True


@pytest.mark.asyncio
async def test_get_published_template_uses_published_dao_query(monkeypatch: pytest.MonkeyPatch) -> None:
    published = template(status='published', version_no=3)
    get_published = AsyncMock(return_value=published)
    monkeypatch.setattr(PipelineDao, 'get_published_template', get_published)

    result = await PipelineTemplateService.get_published(FakeDb(), 'research-test')

    assert result is published
    get_published.assert_awaited_once()


@pytest.mark.asyncio
async def test_template_requires_sections() -> None:
    with pytest.raises(ServiceException) as exc_info:
        await PipelineTemplateService.save_draft(
            FakeDb(),
            template_key='research-test',
            payload=payload(sections=[]),
            operator_id=1,
            operator_name='管理员',
        )
    assert '章节' in exc_info.value.message
