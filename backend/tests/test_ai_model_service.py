"""统一模型配置与真实网关契约的离线测试，不使用旧 Agent/Factory/个人 DAO。"""

import json

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_network
from test_research_simplified_20261025 import raises, seed

env = refactor_env
db = refactor_db
no_external_network = refactor_network


def offline_transport(env, monkeypatch, respond):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        env.gateway.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)
    )
    monkeypatch.setenv('OFFLINE_MODEL_KEY', 'offline-placeholder-key')


@pytest.mark.asyncio
async def test_model_test_runs_minimal_gateway_request_without_exposing_secret(env, db, monkeypatch):
    seed(env, db)
    model = await db.get(env.ai.AiModels, 1)
    model.parameters = {'max_tokens': 32}
    await db.commit()
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={'choices': [{'message': {'content': 'OK'}}], 'usage': {'prompt_tokens': 8, 'completion_tokens': 1}},
        )

    offline_transport(env, monkeypatch, respond)
    result = await env.ai_service.AiModelService.test_ai_model_services(db, 1, True)
    assert result.success and result.model_id == 1 and result.response_preview == 'OK'
    sent = json.loads(requests[0].content)
    assert sent['messages'][-1]['content'] == '请仅回复 OK。' and sent['max_tokens'] == 32
    assert requests[0].headers['authorization'] == 'Bearer offline-placeholder-key'
    assert 'offline-placeholder-key' not in str(result.model_dump())
    audit = db.s.scalars(select(env.configuration.PipelineModelCallAudit)).one()
    assert audit.status == 'success' and audit.input_tokens == 8 and audit.output_tokens == 1


@pytest.mark.asyncio
async def test_model_test_error_is_safe_and_failure_audit_is_committed(env, db, monkeypatch):
    seed(env, db)

    def respond(request):
        return httpx.Response(502, text='authorization=offline-placeholder-key endpoint=https://offline.invalid/v1')

    offline_transport(env, monkeypatch, respond)
    with pytest.raises(env.exc) as caught:
        await env.ai_service.AiModelService.test_ai_model_services(db, 1, True)
    message = caught.value.message
    assert 'offline-placeholder-key' not in message and 'https://offline.invalid' not in message
    db.s.expire_all()
    audit = db.s.scalars(select(env.configuration.PipelineModelCallAudit)).one()
    assert audit.status == 'failed'
    assert 'offline-placeholder-key' not in audit.error and 'https://offline.invalid' not in audit.error


@pytest.mark.asyncio
async def test_add_model_rejects_unsupported_native_protocol_before_persisting(env, db):
    values = {
        'name': '不支持原生协议',
        'provider': 'anthropic',
        'code': 'native',
        'base_url': 'https://offline.invalid',
        'credential_ref': 'env:OFFLINE_MODEL_KEY',
        'capabilities': ['text_generate'],
        'parameters': {},
        'is_enabled': True,
    }
    with pytest.raises(ValidationError):
        env.ai_schema.AiModelModel(**values)
    # 服务端同样检查协议，不能通过绕开 DTO 校验走错 API。
    constructed = env.ai_schema.AiModelModel.model_construct(**values)
    with raises(env, 'OpenAI 兼容协议'):
        await env.ai_service.AiModelService.add_ai_model_services(db, constructed)
    assert not db.s.scalars(select(env.ai.AiModels)).all()


@pytest.mark.asyncio
async def test_model_existence_check_uses_canonical_id_and_no_legacy_owner_scope(env, db):
    seed(env, db)
    result = await env.ai_service.AiModelService.check_ai_model_data_scope_services(db, 1, True)
    assert result.is_success
    with raises(env, '不存在'):
        await env.ai_service.AiModelService.check_ai_model_data_scope_services(db, 999, True)


@pytest.mark.asyncio
async def test_disabled_model_is_rejected_before_transport(env, db, monkeypatch):
    seed(env, db)
    model = await db.get(env.ai.AiModels, 1)
    model.is_enabled = False
    await db.commit()
    calls = []
    offline_transport(env, monkeypatch, lambda request: calls.append(request))
    with raises(env, '已停用'):
        await env.ai_service.AiModelService.test_ai_model_services(db, 1, True)
    assert calls == []


@pytest.mark.asyncio
async def test_image_test_uses_image_capability_and_returns_no_raw_image_or_credentials(env, db, monkeypatch):
    import base64
    from io import BytesIO

    from PIL import Image

    seed(env, db, image=True)
    content = BytesIO()
    Image.new('RGB', (4, 4), 'blue').save(content, format='PNG')
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(content.getvalue()).decode()}]})

    offline_transport(env, monkeypatch, respond)
    result = await env.ai_service.AiModelService.test_ai_model_services(db, 2, True, 'image_generate')
    assert result.success and result.capability == 'image_generate'
    assert requests[0].url.path == '/v1/images/generations'
    assert result.response_preview == f'已验证图片 {len(content.getvalue())} 字节'
    assert 'offline-placeholder-key' not in str(result.model_dump())


@pytest.mark.asyncio
async def test_model_details_do_not_return_credential_reference_or_plain_secret(env, db):
    seed(env, db)
    result = await env.ai_service.AiModelService.ai_model_detail_services(db, 1)
    values = result.model_dump(by_alias=True)
    assert values['credentialRef'] is None and 'apiKey' not in values
    assert 'OFFLINE_MODEL_KEY' not in str(values)
