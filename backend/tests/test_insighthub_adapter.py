import pytest

from config.env import InsightHubSettings
from module_pipeline.integration.insighthub_adapter import InsightHubAdapter


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
