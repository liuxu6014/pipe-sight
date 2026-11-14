"""Global generation bindings are capability checked and frozen into real jobs."""

import importlib
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import payload, queue, seed

env = memory_env
db = memory_db
no_external_network = offline_network


def settings():
    return importlib.import_module('app.intelligence.services.translation_settings')


def extra_model(env, db, identity, capability):
    model = env.ai.AiModels(
        id=identity,
        name=f'模型{identity}',
        provider='compatible',
        code=f'code-{identity}',
        base_url='https://offline.invalid/v1',
        credential_ref='env:OFFLINE_MODEL_KEY',
        capabilities=[capability],
        parameters={},
        is_enabled=True,
    )
    db.add(model)
    return model


@pytest.mark.asyncio
async def test_new_purposes_default_to_unconfigured_and_validate_exact_capabilities(env, db):
    for purpose in ('image', 'digest', 'research'):
        assert await settings().generation_settings(db, purpose) == {'modelId': None}
    seed(env, db, image=True)
    for purpose, model_id in [('image', 1), ('digest', 2), ('research', 2)]:
        with pytest.raises(ValueError, match='能力'):
            await settings().save_generation_settings(db, purpose, model_id)
    image = await env.repo.ResearchDao.get_model(db, 2)
    image.capabilities = ['image_input']
    await db.commit()
    with pytest.raises(ValueError, match='image_generate'):
        await settings().save_generation_settings(db, 'image', 2)
    image.capabilities = ['image_generate']
    image.is_enabled = False
    await db.commit()
    with pytest.raises(ValueError):
        await settings().save_generation_settings(db, 'image', 2)


@pytest.mark.asyncio
async def test_saving_one_purpose_does_not_change_other_bindings_or_template(env, db):
    template, _ = seed(env, db, image=True)
    text_id = 90071992547409931
    extra_model(env, db, text_id, 'text_generate')
    await db.commit()
    assert await settings().save_generation_settings(db, 'research', str(text_id)) == {'modelId': str(text_id)}
    assert await settings().generation_settings(db, 'digest') == {'modelId': '1'}
    assert await settings().generation_settings(db, 'image') == {'modelId': '2'}
    await settings().save_generation_settings(db, 'image', None)
    assert await settings().generation_settings(db, 'research') == {'modelId': str(text_id)}
    assert template.model_id == 1 and template.image_model_id == 2


@pytest.mark.asyncio
async def test_research_job_and_image_assets_use_global_choices_not_template_bindings(env, db, monkeypatch):
    template, _ = seed(env, db, image=True)
    extra_model(env, db, 3, 'text_generate')
    extra_model(env, db, 4, 'image_generate')
    await db.commit()
    await settings().save_generation_settings(db, 'research', 3)
    await settings().save_generation_settings(db, 'image', 4)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db, payload(diagram=True))
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    snapshot = deepcopy(job.config_snapshot)
    assert snapshot['model']['id'] == '3' and snapshot['image_model']['id'] == '4'
    assert snapshot['template']['image_model_id'] == '4'
    assert template.model_id == 1 and template.image_model_id == 2
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    exports = importlib.import_module('app.research.services.exports').ResearchReportExportService
    await exports.queue_images(db, job, report)
    await db.commit()
    assets = await env.repo.ResearchDao.list_assets(db, report.id, 'image')
    assert len(assets) == 1 and assets[0].model_id == 4
    assert assets[0].config_snapshot['model']['id'] == '4'
    call = AsyncMock(return_value='模型输出')
    monkeypatch.setattr(env.gateway.ModelGateway, 'call', call)
    await env.gateway.ResearchModelGenerationService.generate_content(db, snapshot, job.materials, task_id=job.id)
    assert call.await_args.args[1]['id'] == '3'
    await settings().save_generation_settings(db, 'research', 1)
    await settings().save_generation_settings(db, 'image', 2)
    job.status = 'failed'
    await db.commit()
    retry = await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=job.id)
    retried = await env.repo.ResearchDao.get_research_job(db, retry['jobId'], 7)
    assert retried.config_snapshot == snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['daily', 'weekly', 'monthly'])
async def test_all_digest_cadences_use_the_brief_binding(env, db, monkeypatch, kind):
    template, _ = seed(env, db)
    template.purpose = 'digest'
    template.name = '通用简报模板'
    extra_model(env, db, 3, 'text_generate')
    await db.commit()
    await settings().save_generation_settings(db, 'digest', 3)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db, payload(report_type=kind, request_id=kind))
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    assert job.config_snapshot['model']['id'] == '3'
    assert await settings().generation_settings(db, 'research') == {'modelId': '1'}


@pytest.mark.asyncio
async def test_missing_or_invalid_global_choice_never_falls_back_to_a_working_template(env, db, monkeypatch):
    seed(env, db, image=True)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    await settings().save_generation_settings(db, 'research', None)
    with pytest.raises(env.exc) as caught:
        await queue(env, db)
    assert '科研报告生成模型' in caught.value.message
    await settings().save_generation_settings(db, 'research', 1)
    await settings().save_generation_settings(db, 'image', None)
    with pytest.raises(env.exc) as caught:
        await queue(env, db, payload(diagram=True))
    assert '图片生成模型' in caught.value.message
    # Disabled global selection is also an error, even though the template's old model still works.
    model = extra_model(env, db, 3, 'text_generate')
    await db.commit()
    await settings().save_generation_settings(db, 'research', 3)
    model.is_enabled = False
    await db.commit()
    with pytest.raises(env.exc):
        await queue(env, db)


@pytest.mark.asyncio
async def test_automatic_brief_plan_validates_its_own_global_model_before_enabling(env, db):
    template, _ = seed(env, db)
    template.purpose = 'digest'
    template.name = '通用简报模板'
    extra_model(env, db, 3, 'text_generate')
    await db.commit()
    data = {'name': '自动简报', 'template_id': '201', 'report_type': 'daily', 'schedule_time': '08:00'}
    await settings().save_generation_settings(db, 'digest', None)
    with pytest.raises(env.exc) as caught:
        await env.schedules.DigestScheduleService.create(
            db, user_id=7, owner_name='owner', payload=data, template_service=env.template.PipelineTemplateService
        )
    assert '简报生成模型' in caught.value.message
    await settings().save_generation_settings(db, 'digest', 3)
    created = await env.schedules.DigestScheduleService.create(
        db, user_id=7, owner_name='owner', payload=data, template_service=env.template.PipelineTemplateService
    )
    assert created['enabled'] is True
    assert template.model_id == 1
