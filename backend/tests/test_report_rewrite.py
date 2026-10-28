"""局部改写只返回建议，权限与修订冲突在调用模型前检查。"""

import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from test_research_report_metadata import history_fixture
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network

env, db, no_external_network = memory_env, memory_db, offline_network


@pytest.mark.asyncio
async def test_rewrite_returns_proposal_without_saving_report(env: Any, db: Any, monkeypatch: Any) -> None:
    report, _ = history_fixture(env, db)
    service = importlib.import_module('app.research.services.rewrite')
    call = AsyncMock(return_value='改写后的正文')
    monkeypatch.setattr(service.ModelGateway, 'call', call)
    result = await service.ReportRewriteService.propose(db, user_id=7, report_id=301, payload=SimpleNamespace(
        expected_version=1, expected_revision=service.report_revision(report), section_id='local-1',
        start=0, end=4, text='原始正文', mode='polish'))
    assert result['text'] == '改写后的正文'
    assert report.content == '原始正文' and report.version == 1
    assert '不能新增事实' in call.await_args.kwargs['system_prompt']
    assert '无充分依据的判断改成具体的待验证问题' in call.await_args.kwargs['system_prompt']
    assert '给定正文不是原始资料' in call.await_args.kwargs['system_prompt']


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['owner', 'revision', 'selection'])
async def test_rewrite_rejects_invalid_context_before_model(
    env: Any, db: Any, monkeypatch: Any, change: str,
) -> None:
    report, _ = history_fixture(env, db)
    service = importlib.import_module('app.research.services.rewrite')
    call = AsyncMock(return_value='不应调用')
    monkeypatch.setattr(service.ModelGateway, 'call', call)
    body = SimpleNamespace(expected_version=1, expected_revision=service.report_revision(report),
                           section_id='local-1', start=0, end=4, text='原始正文', mode='polish')
    if change == 'revision':
        body.expected_revision = 'stale'
    if change == 'selection':
        body.text = '其他正文'
    with pytest.raises(env.exc):
        await service.ReportRewriteService.propose(db, user_id=8 if change == 'owner' else 7,
                                                  report_id=301, payload=body)
    call.assert_not_awaited()


def test_rewrite_rejects_new_or_missing_citations(env: Any) -> None:
    validate_rewrite = importlib.import_module('app.research.services.rewrite').validate_rewrite
    assert validate_rewrite('原文[1]。', '改写[1]。') == '改写[1]。'
    for candidate in ('改写。', '改写[2]。', '改写[1][1]。', ''):
        with pytest.raises(env.exc):
            validate_rewrite('原文[1]。', candidate)


@pytest.mark.asyncio
async def test_rewrite_uses_real_gateway_with_offline_provider_and_keeps_report(
    env: Any, db: Any, monkeypatch: Any,
) -> None:
    report, _ = history_fixture(env, db)
    service = importlib.import_module('app.research.services.rewrite')
    requests = []
    client = httpx.AsyncClient

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'choices': [{'message': {'content': '离线供应商改写正文'}}]})

    monkeypatch.setenv('OFFLINE_MODEL_KEY', 'offline-test-not-a-secret')
    monkeypatch.setattr(env.gateway.httpx, 'AsyncClient',
                        lambda **kwargs: client(transport=httpx.MockTransport(reply), **kwargs))
    result = await service.ReportRewriteService.propose(db, user_id=7, report_id=301, payload=SimpleNamespace(
        expected_version=1, expected_revision=service.report_revision(report), section_id='local-1',
        start=0, end=4, text='原始正文', mode='polish'))
    assert len(requests) == 1 and result['text'] == '离线供应商改写正文'
    assert report.content == '原始正文' and report.version == 1


@pytest.mark.asyncio
async def test_report_changed_during_model_call_rejects_stale_result(
    env: Any, db: Any, monkeypatch: Any,
) -> None:
    report, _ = history_fixture(env, db)
    service = importlib.import_module('app.research.services.rewrite')
    body = SimpleNamespace(expected_version=1, expected_revision=service.report_revision(report),
                           section_id='local-1', start=0, end=4, text='原始正文', mode='polish')

    async def concurrent_edit(*args: Any, **kwargs: Any) -> str:
        report.content = '其他会话新编辑'
        report.version = 2
        return '过期建议'

    monkeypatch.setattr(service.ModelGateway, 'call', concurrent_edit)
    with pytest.raises(env.exc):
        await service.ReportRewriteService.propose(db, user_id=7, report_id=301, payload=body)
    assert report.content == '其他会话新编辑'
