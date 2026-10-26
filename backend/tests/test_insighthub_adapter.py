from datetime import datetime
from types import SimpleNamespace

import pytest

from app.intelligence.integrations.insighthub import InsightHubAdapter
from config.env import InsightHubSettings


def test_insighthub_content_type_mapping() -> None:
    assert InsightHubAdapter._content_type('rss_feed') == 'RSS'
    assert InsightHubAdapter._content_type('json_api') == 'JSON'
    assert InsightHubAdapter._content_type('web_html') == 'HTML'
    assert InsightHubAdapter._content_type('paper') == 'Other'


def test_insighthub_schema_name_is_validated() -> None:
    InsightHubAdapter(InsightHubSettings(insighthub_db_schema='news'))
    with pytest.raises(ValueError):
        InsightHubAdapter(InsightHubSettings(insighthub_db_schema='news;drop schema public'))


@pytest.mark.asyncio
async def test_insighthub_result_mapping_uses_prompt_trace_as_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        async def fetch(self, *_args: object, **_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    'uuid': 'article-1',
                    'news_id': 7,
                    'create_time': None,
                    'prompt_trace_id': '01TRACE',
                    'ai_title': '处理后标题',
                    'summary': '处理后摘要',
                    'domain_id': 10,
                    'domain': '管道完整性',
                    'classify': 20,
                    'score': 0.87,
                    'warning_grade': None,
                    'warning_cause': None,
                    'focus_risk': None,
                    'suggestion': None,
                    'event_keywords': '管道,监测',
                    'filter_result': None,
                    'del_flag': '0',
                    'processing_status': 'completed',
                }
            ]

        async def close(self) -> None:
            return None

    adapter = InsightHubAdapter(
        InsightHubSettings(insighthub_enabled=True, insighthub_db_password='test-password')
    )

    async def connect() -> FakeConnection:
        return FakeConnection()

    monkeypatch.setattr(adapter, '_connect', connect)
    result = await adapter.fetch_processing_results(['article-1'])

    assert result['article-1']['status'] == 'completed'
    assert result['article-1']['result']['classify'] == 20  # noqa: PLR2004


@pytest.mark.asyncio
async def test_insighthub_result_mapping_recognizes_worker_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        async def fetch(self, *_args: object, **_kwargs: object) -> list[dict[str, object]]:
            return [{'uuid': 'article-1', 'news_id': 7, 'prompt_trace_id': None, 'del_flag': '0', 'processing_status': 'rejected'}]

        async def close(self) -> None:
            return None

    adapter = InsightHubAdapter(
        InsightHubSettings(insighthub_enabled=True, insighthub_db_password='test-password')
    )

    async def connect() -> FakeConnection:
        return FakeConnection()

    monkeypatch.setattr(adapter, '_connect', connect)

    result = await adapter.fetch_processing_results(['article-1'])

    assert result['article-1']['status'] == 'rejected'


@pytest.mark.asyncio
async def test_insighthub_result_mapping_recognizes_worker_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        async def fetch(self, *_args: object, **_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    'uuid': 'article-1',
                    'news_id': 7,
                    'prompt_trace_id': None,
                    'del_flag': '0',
                    'processing_status': 'failed',
                    'processing_error': '模型调用达到最大重试次数',
                }
            ]

        async def close(self) -> None:
            return None

    adapter = InsightHubAdapter(
        InsightHubSettings(insighthub_enabled=True, insighthub_db_password='test-password')
    )

    async def connect() -> FakeConnection:
        return FakeConnection()

    monkeypatch.setattr(adapter, '_connect', connect)

    result = await adapter.fetch_processing_results(['article-1'])

    assert result['article-1']['status'] == 'failed'
    assert result['article-1']['result']['processing_error'] == '模型调用达到最大重试次数'


@pytest.mark.asyncio
async def test_insighthub_result_mapping_exposes_dead_letter_but_keeps_failed_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConnection:
        async def fetch(self, *_args: object, **_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    'uuid': 'article-1',
                    'news_id': 7,
                    'prompt_trace_id': None,
                    'del_flag': '0',
                    'processing_status': 'dead_letter',
                    'processing_attempts': 3,
                    'processing_error': '已达到最大处理次数（3），需人工重试：模型调用超时',
                }
            ]

        async def close(self) -> None:
            return None

    adapter = InsightHubAdapter(
        InsightHubSettings(insighthub_enabled=True, insighthub_db_password='test-password')
    )

    async def connect() -> FakeConnection:
        return FakeConnection()

    monkeypatch.setattr(adapter, '_connect', connect)

    result = await adapter.fetch_processing_results(['article-1'])

    assert result['article-1']['status'] == 'failed'
    assert result['article-1']['processing_status'] == 'dead_letter'
    assert result['article-1']['result']['processing_attempts'] == 3


@pytest.mark.asyncio
async def test_insighthub_retry_clears_previous_worker_filter_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重新交接同一条记录时必须以新 Prompt 快照重新过滤。"""

    class Transaction:
        async def __aenter__(self) -> 'Transaction':
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    class FakeConnection:
        def __init__(self) -> None:
            self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

        def transaction(self) -> Transaction:
            return Transaction()

        async def fetchrow(self, query: str, *args: object) -> dict[str, object] | None:
            if 'data_sources' in query:
                return {'web_source_id': 9}
            if 'articles' in query:
                return {'news_id': 7, 'create_time': datetime(2026, 10, 1), 'prompt_trace_id': None}
            raise AssertionError(f'Unexpected fetchrow query: {query}')

        async def execute(self, query: str, *args: object) -> None:
            self.execute_calls.append((query, args))

        async def close(self) -> None:
            return None

    connection = FakeConnection()
    adapter = InsightHubAdapter(
        InsightHubSettings(insighthub_enabled=True, insighthub_db_password='test-password')
    )

    async def connect() -> FakeConnection:
        return connection

    monkeypatch.setattr(adapter, '_connect', connect)
    source = SimpleNamespace(
        source_id='source-news',
        processor_source_code='pipechina-group-news',
        source_code='pipechina-group-news',
        endpoint='https://example.com/news',
        name='测试来源',
        source_type='news',
    )
    article = SimpleNamespace(
        article_id='article-7',
        title='新版本提示词重跑测试',
        body='正文',
        summary='摘要',
        canonical_url='https://example.com/article-7',
        discovered_time=datetime(2026, 10, 2),
        published_time=datetime(2026, 10, 2),
        tags=['管网'],
        metadata_json={'processing': {'filter': {'promptVersionNo': 2}}},
        article_type='news',
    )

    result = await adapter.submit_articles(source, [article])

    assert result[0]['handoff_status'] == 'dispatched'
    update_sql, update_args = connection.execute_calls[-1]
    assert 'filter_result = NULL' in update_sql
    assert 'processing_attempts = 0' in update_sql
    assert 'processing_started_at = NULL' in update_sql
    assert 'processing_completed_at = NULL' in update_sql
    assert update_args[:2] == (7, datetime(2026, 10, 1))


@pytest.mark.asyncio
async def test_insighthub_resubmits_completed_record_as_new_inbox_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已完成记录重跑时保留历史血缘，并插入新的待处理记录。"""

    class Transaction:
        async def __aenter__(self) -> 'Transaction':
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    class FakeConnection:
        def __init__(self) -> None:
            self.insert_args: tuple[object, ...] | None = None

        def transaction(self) -> Transaction:
            return Transaction()

        async def fetchrow(self, query: str, *_args: object) -> object:
            if 'data_sources' in query:
                return {'web_source_id': 9}
            if 'INSERT INTO' in query and 'articles' in query:
                self.insert_args = _args
                return (8, _args[5])
            if 'articles' in query:
                return {
                    'news_id': 7,
                    'create_time': datetime(2026, 10, 1),
                    'prompt_trace_id': '01OLDTRACE',
                }
            raise AssertionError(f'Unexpected fetchrow query: {query}')

        async def fetchval(self, query: str, *_args: object) -> int:
            assert 'MAX(news_id)' in query
            return 8

        async def execute(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def close(self) -> None:
            return None

    connection = FakeConnection()
    adapter = InsightHubAdapter(
        InsightHubSettings(insighthub_enabled=True, insighthub_db_password='test-password')
    )

    async def connect() -> FakeConnection:
        return connection

    monkeypatch.setattr(adapter, '_connect', connect)
    source = SimpleNamespace(
        source_id='source-news',
        processor_source_code='pipechina-group-news',
        source_code='pipechina-group-news',
        endpoint='https://example.com/news',
        name='测试来源',
        source_type='news',
    )
    article = SimpleNamespace(
        article_id='article-7',
        title='已完成记录重新处理',
        body='正文',
        summary='摘要',
        canonical_url='https://example.com/article-7',
        discovered_time=datetime(2026, 9, 1),
        published_time=datetime(2026, 9, 1),
        tags=['管网'],
        metadata_json={'processing': {'filter': {'promptVersionNo': 2}}},
        article_type='news',
    )

    result = await adapter.submit_articles(source, [article])

    assert result[0]['handoff_status'] == 'processing'
    assert result[0]['handoff_record_id'] == '8'
    assert connection.insert_args is not None
    assert connection.insert_args[5] > datetime(2026, 10, 1)
