"""资料篮真实外键、实时标题与私人资料权限。"""

from types import SimpleNamespace as NS

import pytest
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_no_external_network
from test_research_simplified_20261025 import raises, seed

env = refactor_env
db = refactor_db
no_external_network = refactor_no_external_network


@pytest.mark.asyncio
async def test_list_items_resolves_live_titles_and_no_persisted_snapshot(env, db):
    _, file = seed(env, db)
    service = env.app.ResearchWorkspaceService
    await service.upsert_item(
        db,
        7,
        NS(item_type='file', item_id=file.id, action='basket', title='伪造标题', snapshot={'content': '伪造正文'}),
    )
    file.name = '更新后的资料名'
    await db.commit()
    result = await service.list_items(db, 7)
    assert result['basket'] == [{'id': str(file.id), 'type': 'file', 'title': '更新后的资料名'}]
    row = (await env.repo.ResearchDao.list_workspace_items(db, 7))[0]
    assert row.file_id == file.id and not hasattr(row, 'snapshot')


@pytest.mark.asyncio
async def test_workspace_is_idempotent_and_delete_only_removes_relation(env, db):
    _, file = seed(env, db)
    service = env.app.ResearchWorkspaceService
    payload = NS(item_type='material', item_id=file.id, action='favorite')
    await service.upsert_item(db, 7, payload)
    await service.upsert_item(db, 7, payload)
    assert len(await env.repo.ResearchDao.list_workspace_items(db, 7)) == 1
    await service.delete_item(db, 8, file.id, 'favorite')
    assert len(await env.repo.ResearchDao.list_workspace_items(db, 7)) == 1
    await service.delete_item(db, 7, file.id, 'favorite')
    assert not await env.repo.ResearchDao.list_workspace_items(db, 7)
    assert await env.library_repo.MaterialDao.get_owned_material(db, file.id, 7)


@pytest.mark.asyncio
async def test_workspace_rejects_other_users_file(env, db):
    _, file = seed(env, db)
    with raises(env, '无权'):
        await env.app.ResearchWorkspaceService.upsert_item(
            db, 8, NS(item_type='file', item_id=file.id, action='basket')
        )
