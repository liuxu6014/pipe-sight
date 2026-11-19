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
    assert (await service.install_builtins(db, user_id=7))['created'] == 9
    first = (await repo.list_templates(db, user_id=7))[0]
    first.prompt, first.is_enabled = '保留用户自行编写的提示词', False
    await db.commit()
    assert (await service.install_builtins(db, user_id=8))['created'] == 9
    assert (await service.install_builtins(db, user_id=7))['created'] == 0
    assert first.prompt == '保留用户自行编写的提示词' and not first.is_enabled
    a, b = await repo.list_templates(db, user_id=7), await repo.list_templates(db, user_id=8)
    assert len(a) == len(b) == 9 and not ({r.id for r in a} & {r.id for r in b})
    assert all(r.purpose == 'research' for r in b)


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
    assert (await service.list_templates(db, user_id=7))['total'] == 8
    deleted = (await service.list_templates(db, user_id=7, include_deleted=True))['rows']
    assert len(deleted) == 9 and next(r for r in deleted if r['id'] == str(ident))['isDeleted']
    with pytest.raises(env.exc):
        await service.save_draft(
            db, template_key=ident, payload=template_data(), operator_id=7, operator_name='', user_id=7
        )
    await service.restore(db, ident, user_id=7)
    assert row.preset_key == key and row.prompt == '保留我的提示词' and row.name == '我改过的模板名称'
    assert not row.is_enabled and row.deleted_at is None
    assert (await service.list_templates(db, user_id=7))['total'] == 9


@pytest.mark.asyncio
async def test_existing_default_is_adopted_without_overwriting_edits_or_edit_time(env, db) -> None:
    service, repo = env.template.PipelineTemplateService, env.repo.ResearchDao
    template, _ = seed(env, db)
    template.name, template.purpose, template.report_type = '生产痛点与关键技术攻关需求', 'research', 'research-demand'
    template.prompt, template.is_enabled = '已改写的个人内容', False
    await db.commit()
    before = template.updated_at
    assert (await service.install_builtins(db, user_id=7))['created'] == 8
    assert template.preset_key and template.updated_at == before
    assert template.prompt == '已改写的个人内容' and not template.is_enabled
    assert len(await repo.list_templates(db, user_id=7)) == 9


@pytest.mark.asyncio
async def test_all_legacy_digest_templates_are_hidden_without_changing_saved_content(env, db) -> None:
    service, repo = env.template.PipelineTemplateService, env.repo.ResearchDao
    legacy, _ = seed(env, db)
    legacy.purpose, legacy.name = 'digest', '管网科技情报日报'
    legacy.prompt = '保留历史日报提示词及引用用途'
    await db.commit()
    for frequency in ('weekly', 'monthly'):
        await service.get_fixed_digest(db, frequency, 7)
    await db.commit()
    for published_only in (False, True):
        result = await service.list_templates(db, user_id=7, published_only=published_only)
        assert result['total'] == 0 and result['rows'] == []
        page = await service.list_templates(db, user_id=7, published_only=published_only, page=1)
        assert page['total'] == 0 and page['counts'] == {'all': 0}
    saved = await repo.get_template(db, legacy.id, user_id=7)
    assert saved is not None and saved.prompt == '保留历史日报提示词及引用用途' and saved.is_enabled
    assert len(await repo.list_templates(db, user_id=7)) == 3


@pytest.mark.asyncio
async def test_fixed_digest_is_owner_scoped_repeatable_and_cannot_be_managed(env, db):
    service = env.template.PipelineTemplateService
    a = await service.get_fixed_digest(db, 'weekly', 7)
    same = await service.get_fixed_digest(db, 'weekly', 7)
    b = await service.get_fixed_digest(db, 'weekly', 8)
    monthly = await service.get_fixed_digest(db, 'monthly', 7)
    assert a.id == same.id and len({a.id, b.id, monthly.id}) == 3
    assert a.sections == [] and a.image_config == {'enabled': False}
    assert a.preset_key == 'digest-fixed-v1-weekly' and a.digest_cadence == 'weekly'
    assert await service.get_published(db, a.id, 8) is None
    for action in ('publish', 'retire', 'archive', 'restore'):
        with pytest.raises(env.exc):
            await getattr(service, action)(db, a.id, user_id=7)
    for data, template_key in (
        ({'purpose': 'digest', 'name': '新简报', 'prompt': '自定义'}, None),
        (template_data(), a.id),
    ):
        with pytest.raises(env.exc):
            await service.save_draft(
                db, template_key=template_key, payload=data, operator_id=7, operator_name='', user_id=7
            )
    assert a.is_enabled and a.deleted_at is None
    for frequency in ('daily', 'all', 'unknown'):
        with pytest.raises(env.exc):
            await service.get_fixed_digest(db, frequency, 7)


@pytest.mark.asyncio
async def test_digest_save_as_is_a_new_private_template_reusable_with_its_ordered_rules(env, db):
    service = env.template.PipelineTemplateService
    await service.install_builtins(db, user_id=7, purpose='digest')
    catalog = await service.list_templates(db, category='digest', published_only=True, user_id=7)
    source = next(row for row in catalog['rows'] if row['digestCadence'] == 'weekly')
    rules = [{'name': '投运', 'prompt': '须有投运日期'}, {'name': '验证', 'prompt': '须有试验结果'}]
    saved = await service.save_draft(
        db,
        template_key=None,
        payload={
            'name': '项目跟踪周报',
            'purpose': 'digest',
            'digest_cadence': 'weekly',
            'prompt': source['prompt'],
            'screening_prompt': '仅当期新增事实',
            'screening_categories': rules,
        },
        operator_id=None,
        operator_name='',
        user_id=7,
    )
    db.s.expire_all()
    for published in (True, False):
        listing = await service.list_templates(db, category='digest', published_only=published, user_id=7)
        by_id = {row['id']: row for row in listing['rows']}
        assert len(by_id) == len(catalog['rows']) + 1
        assert by_id[source['id']]['screeningCategories'] == source['screeningCategories']
        assert by_id[saved['id']]['screeningCategories'] == rules
        assert by_id[saved['id']]['screeningPrompt'] == '仅当期新增事实'
        assert by_id[saved['id']]['prompt'] == source['prompt']
    assert await service.get_published(db, saved['id'], 8) is None


@pytest.mark.asyncio
async def test_personal_digest_defaults_can_be_edited_and_selected_only_by_their_owner(env, db):
    service = env.template.PipelineTemplateService
    assert await service.install_builtins(db, user_id=7, purpose='digest') == {'created': 2}
    assert await service.install_builtins(db, user_id=8, purpose='digest') == {'created': 2}
    choices = await service.list_templates(db, category='digest', published_only=True, user_id=7)
    for cadence in ('weekly', 'monthly'):
        system_template = await service.get_fixed_digest(db, cadence, 7)
        assert choices['defaultWritingPrompts'][cadence] == system_template.prompt
    weekly = next(item for item in choices['rows'] if item['digestCadence'] == 'weekly')
    assert weekly['screeningCategories'] == choices['defaultScreeningCategories']
    assert [entry['name'] for entry in choices['defaultScreeningCategories']] == ['技术进展', '工程应用', '行业动态']
    assert len({entry['prompt'] for entry in choices['defaultScreeningCategories']}) == 3
    edits = {
        'purpose': 'digest',
        'digest_cadence': 'weekly',
        'name': '检测专题周报',
        'prompt': '突出检测技术及适用范围',
        'screening_prompt': '排除没有实际检测数据的文章',
    }
    saved = await service.save_draft(
        db, template_key=weekly['id'], payload=edits, operator_id=7, operator_name='', user_id=7
    )
    assert saved['screeningPrompt'] == edits['screening_prompt']
    assert saved['screeningCategories'] == []  # A pre-category client saved its own screening rule.
    categories = [
        {'name': '现场试验', 'prompt': '纳入有现场验证结果的报道'},
        {'name': '标准', 'prompt': '纳入正式颁布的标准'},
    ]
    await service.save_draft(
        db,
        template_key=weekly['id'],
        payload={**edits, 'screening_categories': categories},
        operator_id=7,
        operator_name='',
        user_id=7,
    )
    saved = await service.save_draft(
        db, template_key=weekly['id'], payload=edits, operator_id=7, operator_name='', user_id=7
    )
    assert saved['screeningCategories'] == categories  # Omitted on a later edit.
    available = await service.list_templates(db, category='digest', published_only=True, user_id=7)
    assert next(item for item in available['rows'] if item['id'] == weekly['id'])['screeningCategories'] == categories
    assert all(
        item['screeningCategories'] == choices['defaultScreeningCategories']
        for item in (await service.list_templates(db, category='digest', published_only=True, user_id=8))['rows']
    )
    management = await service.list_templates(db, category='digest', page=1, user_id=7)
    assert management['defaultScreeningCategories'] == choices['defaultScreeningCategories']
    assert all('screeningCategories' not in item for item in management['rows'])
    cleared = await service.save_draft(
        db,
        template_key=weekly['id'],
        payload={**edits, 'screening_categories': [], 'screening_prompt': ''},
        operator_id=7,
        operator_name='',
        user_id=7,
    )
    assert cleared['screeningCategories'] == []
    assert (await service.get_digest_for_run(db, 'weekly', 7, weekly['id'])).prompt == edits['prompt']
    for account, cadence in ((8, 'weekly'), (7, 'monthly')):
        with pytest.raises(env.exc):
            await service.get_digest_for_run(db, cadence, account, weekly['id'])
    with pytest.raises(env.exc):
        await service.save_draft(
            db, template_key=weekly['id'], payload=edits, operator_id=8, operator_name='', user_id=8
        )
    await service.archive(db, weekly['id'], user_id=7)
    assert await service.install_builtins(db, user_id=7, purpose='digest') == {'created': 0}
    assert (await service.list_templates(db, category='digest', published_only=True, user_id=7))['total'] == 1
    assert (await service.list_templates(db, category='digest', published_only=True, user_id=8))['total'] == 2


@pytest.mark.asyncio
async def test_fixed_digest_creation_is_rolled_back_with_failed_admission(env, db):
    service, repo = env.template.PipelineTemplateService, env.repo.ResearchDao
    legacy, _ = seed(env, db)
    legacy.purpose, legacy.name, legacy.prompt = 'digest', '管网科技情报周报', '用户历史提示词'
    await db.commit()
    original_id = legacy.id
    internal = await service.get_fixed_digest(db, 'weekly', 7)
    internal_id = internal.id
    assert internal_id != original_id
    db.s.rollback()
    assert await repo.get_template(db, internal_id, 7) is None
    saved = await repo.get_template(db, original_id, 7)
    assert saved.prompt == '用户历史提示词' and saved.name == '管网科技情报周报'


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
        await schedules.create(
            db,
            user_id=8,
            owner_name='另一账号',
            template_service=env.template.PipelineTemplateService,
            payload={
                'name': '越权模板计划',
                'report_type': 'weekly',
                'template_id': str(template.id),
                'enabled': False,
            },
        )
    call.assert_not_awaited()
