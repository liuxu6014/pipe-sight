"""Real-session ownership checks; never substitute the template repository."""

import importlib
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import payload, queue, seed

env, db, no_external_network = memory_env, memory_db, offline_network


def template_data() -> dict:
    return {
        'name': '同名个人模板',
        'purpose': 'research',
        'report_type': 'research-demand',
        'prompt': '只使用所选资料，准确保留引用。',
        'sections': [{'id': 1, 'title': '技术现状', 'words': 500}],
        'user_id': 8,
    }


@pytest.mark.asyncio
async def test_real_sessions_scope_create_list_edit_and_enable_to_each_user(env, db) -> None:
    service, repo = env.template.PipelineTemplateService, env.repo.ResearchDao
    a = await service.save_draft(
        db, template_key=None, payload=template_data(), operator_id=7, operator_name='', user_id=7
    )
    b = await service.save_draft(
        db, template_key=None, payload=template_data(), operator_id=8, operator_name='', user_id=8
    )
    assert a['id'] != b['id']
    assert (await repo.get_template(db, a['id'])).user_id == 7  # Forged payload owner is ignored.
    assert [r['id'] for r in (await service.list_templates(db, user_id=7))['rows']] == [a['id']]
    assert [r['id'] for r in (await service.list_templates(db, user_id=8))['rows']] == [b['id']]
    assert await service.get_published(db, a['id'], 8) is None
    before = deepcopy((await repo.get_template(db, a['id'])).sections)
    for operation in ('edit', 'retire', 'publish'):
        with pytest.raises(env.exc):
            if operation == 'edit':
                await service.save_draft(
                    db, template_key=a['id'], payload=template_data(), operator_id=8, operator_name='', user_id=8
                )
            else:
                await getattr(service, operation)(db, a['id'], user_id=8)
    row = await repo.get_template(db, a['id'])
    assert row.sections == before and row.is_enabled and row.user_id == 7
    await service.retire(db, a['id'], user_id=7)
    assert (await service.list_templates(db, user_id=7, published_only=True))['rows'] == []
    assert (await service.publish(db, a['id'], user_id=7))['isEnabled']


@pytest.mark.asyncio
async def test_builtins_are_private_repeatable_and_never_overwrite_user_edits(env, db) -> None:
    service, repo = env.template.PipelineTemplateService, env.repo.ResearchDao
    assert (await service.install_builtins(db, user_id=7))['created'] == 12
    first = (await repo.list_templates(db, user_id=7))[0]
    first.prompt, first.is_enabled = '保留用户自行编写的提示词', False
    await db.commit()
    assert (await service.install_builtins(db, user_id=8))['created'] == 12
    assert (await service.install_builtins(db, user_id=7))['created'] == 0
    assert first.prompt == '保留用户自行编写的提示词' and not first.is_enabled
    a, b = await repo.list_templates(db, user_id=7), await repo.list_templates(db, user_id=8)
    assert len(a) == len(b) == 12 and not ({r.id for r in a} & {r.id for r in b})
    assert {service.digest_cadence(r) for r in b if r.purpose == 'digest'} == {'daily', 'weekly', 'monthly'}


@pytest.mark.asyncio
async def test_generation_and_automatic_schedules_reject_foreign_templates_before_model(env, db, monkeypatch) -> None:
    template, _ = seed(env, db)
    call = AsyncMock()
    monkeypatch.setattr(env.gateway.ModelGateway, 'call', call)
    with pytest.raises(env.exc):
        await queue(env, db, payload(template_id=str(template.id)), user_id=8)
    template.purpose, template.name = 'digest', '管网科技情报周报'
    await db.commit()
    schedules = importlib.import_module('app.research.services.digest_schedules').DigestScheduleService
    with pytest.raises(env.exc):
        await schedules._validate_enabled_template(
            db, template.id, {}, env.template.PipelineTemplateService, frequency='weekly', user_id=8
        )
    call.assert_not_awaited()
