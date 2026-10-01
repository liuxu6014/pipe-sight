from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from exceptions.exception import ServiceException
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.service import pipeline_collection_service
from module_pipeline.service.pipeline_prompt_service import PipelinePromptService

PROMPT_VERSION = 3


def _prompt(**overrides) -> SimpleNamespace:
    values = {
        'prompt_id': 'prompt-1',
        'prompt_key': 'data-filter',
        'scene': 'data-filter',
        'name': '数据过滤与清洗',
        'description': '对采集内容进行领域相关性和风险筛选',
        'system_prompt': '你是管网科技情报过滤器。输入 {{title}} 和 {{body}}。',
        'user_prompt': '标题：{{title}}\n正文：{{body}}\n来源：{{source}}',
        'version_no': 1,
        'status': 'draft',
        'test_status': 'untested',
        'test_result': {},
        'operator_id': 1,
        'operator_name': '管理员',
        'published_at': None,
        'create_time': None,
        'update_time': None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_prompt_test_requires_filter_output_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    prompt = _prompt(user_prompt='标题：{{title}}\n正文：{{body}}')
    monkeypatch.setattr(PipelineDao, 'get_latest_prompt', AsyncMock(return_value=prompt))

    with pytest.raises(ServiceException) as exc_info:
        await PipelinePromptService.test_prompt(SimpleNamespace(), 'data-filter')
    assert 'keep' in exc_info.value.message


@pytest.mark.asyncio
async def test_prompt_publish_requires_passed_test_and_returns_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    prompt = _prompt(test_status='passed', status='draft')
    monkeypatch.setattr(PipelineDao, 'get_latest_prompt', AsyncMock(return_value=prompt))
    monkeypatch.setattr(PipelineDao, 'list_prompt_versions', AsyncMock(return_value=[prompt]))
    monkeypatch.setattr(PipelineDao, 'add_prompt', AsyncMock())
    db = _FakeDb()

    result = await PipelinePromptService.publish_prompt(db, 'data-filter', operator_id=1, operator_name='管理员')

    assert result['promptKey'] == 'data-filter'
    assert result['status'] == 'published'
    assert prompt.status == 'published'
    assert db.committed is True


@pytest.mark.asyncio
async def test_collect_run_uses_published_prompt_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    prompt = _prompt(status='published', test_status='passed', version_no=PROMPT_VERSION)
    monkeypatch.setattr(
        pipeline_collection_service.PipelinePromptService,
        'get_published_prompt',
        AsyncMock(return_value=prompt),
    )
    monkeypatch.setattr(pipeline_collection_service, '_pipechina_records', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(pipeline_collection_service.PipelineCollectionService, '_save_articles', AsyncMock(return_value=(0, 0, 0)))

    source = SimpleNamespace(
        source_id='src-1', name='来源', adapter_key='pipechina_group_news', endpoint='https://example.test',
        config_json={'limit': 1}, last_run_time=None, last_run_status=None, success_count=0, consecutive_failures=0,
    )
    db = _CollectionDb(source)
    result = await pipeline_collection_service.PipelineCollectionService.collect_source(db, source)

    assert result['status'] == 'success'
    run = db.added[0]
    assert run.config_snapshot['filterPrompt']['promptKey'] == 'data-filter'
    assert run.config_snapshot['filterPrompt']['versionNo'] == PROMPT_VERSION


class _FakeDb:
    committed = False

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _item: object) -> None:
        return None


class _CollectionDb(_FakeDb):
    def __init__(self, source: object) -> None:
        self.added = []
        self.source = source
        self.execute_count = 0

    def add(self, item: object) -> None:
        self.added.append(item)

    async def execute(self, _query: object) -> '_Result':
        self.execute_count += 1
        return _Result(self.source if self.execute_count == 1 else self.added[0])

    async def rollback(self) -> None:
        return None


class _Result:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalars(self) -> '_Result':
        return self

    def one(self) -> object:
        return self.value

    def first(self) -> object:
        return self.value
