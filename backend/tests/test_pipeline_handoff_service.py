from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.integration.insighthub_adapter import InsightHubAdapter
from module_pipeline.service.pipeline_domain_service import PipelineDomainService


@pytest.mark.asyncio
async def test_collection_task_exposes_latest_handoff_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SimpleNamespace(source_id='source-news', name='科技资讯源', schedule_cron=None)
    run = SimpleNamespace(
        run_id='run-1',
        source_id=source.source_id,
        status='success',
        handoff_status='processing',
        handoff_count=4,
        handoff_processed_count=3,
        handoff_failed_count=0,
        error_message=None,
    )
    monkeypatch.setattr(PipelineDao, 'list_sources', AsyncMock(return_value=[source]))
    monkeypatch.setattr(PipelineDao, 'list_collection_runs', AsyncMock(return_value=[run]))

    result = await PipelineDomainService.list_collection_tasks(SimpleNamespace())

    assert result['rows'][0]['latest_run_id'] == 'run-1'
    assert result['rows'][0]['handoff_progress'] == 75  # noqa: PLR2004


@pytest.mark.asyncio
async def test_external_handoff_persists_article_and_run_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(
        run_id='run-1',
        source_id='source-news',
        handoff_status='pending',
        handoff_error=None,
        handoff_time=None,
        handoff_batch_id=None,
        handoff_count=0,
        handoff_processed_count=0,
        handoff_failed_count=0,
    )
    source = SimpleNamespace(source_id='source-news', handoff_mode='external')
    article = SimpleNamespace(
        article_id='article-1',
        handoff_status='pending',
        handoff_batch_id=None,
        handoff_record_id=None,
        handoff_result_json={},
        handoff_time=None,
        handoff_error=None,
    )
    query_db = SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(PipelineDao, 'get_collection_run', AsyncMock(return_value=run))
    monkeypatch.setattr(PipelineDao, 'get_source', AsyncMock(return_value=source))
    monkeypatch.setattr(PipelineDao, 'list_handoff_articles', AsyncMock(return_value=[article]))
    monkeypatch.setattr(
        InsightHubAdapter,
        'submit_articles',
        AsyncMock(
            return_value=[
                {
                    'article_id': article.article_id,
                    'handoff_record_id': '7',
                    'handoff_create_time': datetime(2026, 8, 24, 12, 0),
                    'handoff_status': 'processing',
                }
            ]
        ),
    )

    result = await PipelineDomainService.dispatch_insighthub_handoff(query_db, run.run_id)

    assert result['handoff_count'] == 1
    assert article.handoff_record_id == '7'
    assert article.handoff_status == 'processing'
    assert run.handoff_status == 'dispatched'
    query_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_external_handoff_sync_persists_processed_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(
        run_id='run-1',
        handoff_status='processing',
        handoff_processed_count=0,
        handoff_failed_count=0,
        handoff_time=None,
    )
    article = SimpleNamespace(
        article_id='article-1',
        handoff_record_id='7',
        handoff_status='processing',
        handoff_trace_id=None,
        handoff_result_json={},
        handoff_time=None,
        handoff_error=None,
    )
    query_db = SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(PipelineDao, 'get_collection_run', AsyncMock(return_value=run))
    monkeypatch.setattr(PipelineDao, 'list_handoff_articles', AsyncMock(return_value=[article]))
    monkeypatch.setattr(
        InsightHubAdapter,
        'fetch_processing_results',
        AsyncMock(
            return_value={
                article.article_id: {
                    'status': 'completed',
                    'news_id': 7,
                    'prompt_trace_id': '01TRACE',
                    'result': {'domain': '管道完整性', 'score': 0.91},
                }
            }
        ),
    )

    result = await PipelineDomainService.sync_insighthub_handoff(query_db, run.run_id)

    assert result['handoff_status'] == 'completed'
    assert article.handoff_trace_id == '01TRACE'
    assert article.handoff_result_json['domain'] == '管道完整性'
    query_db.commit.assert_awaited_once()
