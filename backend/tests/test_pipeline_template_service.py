"""规范模板与无模型配置门槛；无版本审批状态机。"""

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_no_external_network
from test_research_simplified_20261025 import raises, seed

env = refactor_env
db = refactor_db
no_external_network = refactor_no_external_network


@pytest.mark.asyncio
async def test_save_template_can_remain_unconfigured(env, db):
    result = await env.template.PipelineTemplateService.save_draft(
        db,
        template_key=None,
        payload={'purpose': 'research', 'name': '测试模板', 'prompt': '只使用实际资料', 'sections': []},
        operator_id=7,
        operator_name='管理员',
    )
    assert result['id'].isdecimal() and result['modelId'] is None
    row = await env.repo.ResearchDao.get_template(db, result['id'])
    assert row.model_id is None and row.is_enabled
    assert not hasattr(row, 'version_no')


@pytest.mark.asyncio
async def test_enable_disable_keeps_same_template_id(env, db):
    seed(env, db, model=False)
    await env.template.PipelineTemplateService.retire(db, '201')
    assert await env.template.PipelineTemplateService.get_published(db, '201') is None
    result = await env.template.PipelineTemplateService.publish(db, '201', operator_id=7, operator_name='管理员')
    assert result['id'] == '201' and result['isEnabled']
    assert len(await env.repo.ResearchDao.list_templates(db)) == 1


@pytest.mark.asyncio
async def test_get_available_uses_research_repository(env, monkeypatch):
    row = NS(is_enabled=True)
    get = AsyncMock(return_value=row)
    monkeypatch.setattr(env.repo.ResearchDao, 'get_template', get)
    database = object()
    assert await env.template.PipelineTemplateService.get_published(database, '201') is row
    get.assert_awaited_once_with(database, 201)


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('prompt', ' '), ('name', ''), ('purpose', 'review')])
async def test_template_rejects_invalid_required_fields(env, db, field, value):
    data = {'purpose': 'research', 'name': '模板', 'prompt': '提示词', field: value}
    with pytest.raises(env.exc):
        await env.template.PipelineTemplateService.save_draft(
            db, template_key=None, payload=data, operator_id=7, operator_name='管理员'
        )


@pytest.mark.asyncio
async def test_listing_exposes_readiness_without_hiding_unconfigured_templates(env, db):
    template, _ = seed(env, db, model=False)
    result = await env.template.PipelineTemplateService.list_templates(db, published_only=True)
    assert result['total'] == 1 and result['rows'][0]['modelConfigured'] is False
    assert result['rows'][0]['imageModelConfigured'] is False
    template.is_enabled = False
    await db.commit()
    assert (await env.template.PipelineTemplateService.list_templates(db, published_only=True))['total'] == 0


@pytest.mark.asyncio
async def test_missing_text_model_is_a_generation_error_not_template_approval(env, db):
    seed(env, db, model=False)
    with raises(env, 'text_generate'):
        await env.template.PipelineTemplateService.validate_models(db, None)


@pytest.mark.asyncio
@pytest.mark.parametrize('template_key', [None, '201'])
async def test_template_model_references_are_int_before_persist_and_exact_strings_on_wire(
    env, monkeypatch, template_key
):
    from app.intelligence.schemas.pipeline import PipelineTemplateSaveModel

    text_id, image_id = 9007199254740993, 9007199254740995
    payload = PipelineTemplateSaveModel(
        name='大编号模型模板',
        purpose='research',
        prompt='仅使用实际资料',
        model_id=str(text_id),
        image_model_id=str(image_id),
    ).model_dump()
    assert payload['model_id'] == str(text_id) and payload['image_model_id'] == str(image_id)
    original = dict(payload)
    stored = env.configuration.PipelineTemplateVersion(id=201, is_enabled=True)
    models = {
        text_id: NS(is_enabled=True, provider='compatible', capabilities=['text_generate']),
        image_id: NS(is_enabled=True, provider='compatible', capabilities=['image_generate']),
    }

    async def get_model(database, identity):
        assert type(identity) is int  # Check before any driver can coerce it.
        return models[identity]

    def assert_persist_types():
        row = database.add.call_args.args[0] if template_key is None else stored
        assert type(row.model_id) is int and row.model_id == text_id
        assert type(row.image_model_id) is int and row.image_model_id == image_id

    async def refresh(row):
        row.id = 201

    database = NS(
        add=Mock(), commit=AsyncMock(side_effect=assert_persist_types), refresh=AsyncMock(side_effect=refresh)
    )
    monkeypatch.setattr(env.repo.ResearchDao, 'get_model', get_model)
    monkeypatch.setattr(env.repo.ResearchDao, 'get_template', AsyncMock(return_value=stored))
    result = await env.template.PipelineTemplateService.save_draft(
        database, template_key=template_key, payload=payload, operator_id=7, operator_name='管理员'
    )
    assert payload == original
    database.commit.assert_awaited_once()
    assert result['modelId'] == str(text_id) and result['imageModelId'] == str(image_id)


def test_template_model_references_preserve_large_ids_and_nulls_in_output(env):
    row = env.configuration.PipelineTemplateVersion(
        id=201,
        name='模板',
        purpose='research',
        prompt='提示词',
        sections=[],
        image_config={},
        model_id=9007199254740993,
        image_model_id=9007199254740995,
        is_enabled=True,
    )
    result = env.template.PipelineTemplateService._dict(row)
    assert result['modelId'] == '9007199254740993'
    assert result['imageModelId'] == '9007199254740995'
    row.model_id = row.image_model_id = None
    result = env.template.PipelineTemplateService._dict(row)
    assert result['modelId'] is None and result['imageModelId'] is None
