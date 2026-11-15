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
    assert (await service.install_builtins(db, user_id=7))['created'] == 11
    first = (await repo.list_templates(db, user_id=7))[0]
    first.prompt, first.is_enabled = '保留用户自行编写的提示词', False
    await db.commit()
    assert (await service.install_builtins(db, user_id=8))['created'] == 11
    assert (await service.install_builtins(db, user_id=7))['created'] == 0
    assert first.prompt == '保留用户自行编写的提示词' and not first.is_enabled
    a, b = await repo.list_templates(db, user_id=7), await repo.list_templates(db, user_id=8)
    assert len(a) == len(b) == 11 and not ({r.id for r in a} & {r.id for r in b})
    assert {service.digest_cadence(r) for r in b if r.purpose == 'digest'} == {'weekly', 'monthly'}
    weekly = next(r for r in b if service.digest_cadence(r) == 'weekly')
    weekly.name = '我自己的检测情报'
    assert service.digest_cadence(weekly) == 'weekly'


@pytest.mark.asyncio
async def test_default_identity_survives_rename_delete_refresh_and_restore(env, db) -> None:
    service, repo = env.template.PipelineTemplateService, env.repo.ResearchDao
    await service.install_builtins(db, user_id=7)
    row = (await repo.list_templates(db, user_id=7))[0]
    ident, key = row.id, row.preset_key
    row.name, row.prompt = '我改过的模板名称', '保留我的提示词'
    await db.commit()
    assert (await service.install_builtins(db, user_id=7))['created'] == 0
    for action in ('archive', 'restore'):
        with pytest.raises(env.exc):
            await getattr(service, action)(db, ident, user_id=8)
    await service.archive(db, ident, user_id=7)
    assert await service.get_published(db, ident, user_id=7) is None
    assert (await service.install_builtins(db, user_id=7))['created'] == 0
    assert (await service.list_templates(db, user_id=7))['total'] == 10
    deleted = (await service.list_templates(db, user_id=7, include_deleted=True))['rows']
    assert len(deleted) == 11 and next(r for r in deleted if r['id'] == str(ident))['isDeleted']
    with pytest.raises(env.exc):
        await service.save_draft(db, template_key=ident, payload=template_data(), operator_id=7, operator_name='', user_id=7)
    await service.restore(db, ident, user_id=7)
    assert row.preset_key == key and row.prompt == '保留我的提示词' and row.name == '我改过的模板名称'
    assert not row.is_enabled and row.deleted_at is None
    assert (await service.list_templates(db, user_id=7))['total'] == 11


@pytest.mark.asyncio
async def test_existing_default_is_adopted_without_overwriting_edits_or_edit_time(env, db) -> None:
    service, repo = env.template.PipelineTemplateService, env.repo.ResearchDao
    template, _ = seed(env, db)
    template.name, template.purpose, template.report_type = '生产痛点与关键技术攻关需求', 'research', 'research-demand'
    template.prompt, template.is_enabled = '已改写的个人内容', False
    await db.commit()
    before = template.updated_at
    assert (await service.install_builtins(db, user_id=7))['created'] == 10
    assert template.preset_key and template.updated_at == before
    assert template.prompt == '已改写的个人内容' and not template.is_enabled
    assert len(await repo.list_templates(db, user_id=7)) == 11


@pytest.mark.asyncio
async def test_legacy_daily_template_is_hidden_without_changing_saved_content(env, db) -> None:
    service, repo = env.template.PipelineTemplateService, env.repo.ResearchDao
    legacy, _ = seed(env, db)
    legacy.purpose, legacy.name = 'digest', '管网科技情报日报'
    legacy.prompt = '保留历史日报提示词及引用用途'
    await db.commit()
    for name in ('管网科技情报周报', '管网科技情报月报'):
        await service.save_draft(
            db,
            template_key=None,
            payload={'purpose': 'digest', 'name': name, 'prompt': '根据公开资料编制简报'},
            operator_id=7,
            operator_name='',
            user_id=7,
        )
    for published_only in (False, True):
        result = await service.list_templates(db, user_id=7, published_only=published_only)
        assert result['total'] == 2
        assert {r['digestCadence'] for r in result['rows']} == {'weekly', 'monthly'}
    saved = await repo.get_template(db, legacy.id, user_id=7)
    assert saved is not None and saved.prompt == '保留历史日报提示词及引用用途' and saved.is_enabled
    assert len(await repo.list_templates(db, user_id=7)) == 3


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
