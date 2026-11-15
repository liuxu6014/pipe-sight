"""HTTP endpoints + real repository/session, with two authenticated principals.

SQLite runs normally; the same scenario runs on isolated PG18 via the full runner.
Authentication alone is substituted; ownership SQL and write services are real.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from test_published_template_api import current_user, portal_app
from test_research_report_functional_integration import env as report_env
from test_research_report_functional_integration import report_case as isolated_report_case

from app.intelligence.api.controller import PipelineTemplateService
from app.system.services.authentication import LoginService
from common.aspect.db_seesion import DBSessionDependency

env, report_case = report_env, isolated_report_case


@pytest.mark.asyncio
async def test_two_principals_cannot_list_modify_or_use_each_others_templates(env, report_case, monkeypatch) -> None:
    from unittest.mock import AsyncMock

    a = report_case.owner
    b = report_case.db.s.scalar(text('SELECT id FROM sys_user WHERE id <> :owner ORDER BY id LIMIT 1'), {'owner': a})
    if b is None:
        assert report_case.kind == 'sqlite'
        b = a + 1
        report_case.db.s.execute(text('INSERT INTO sys_user(id) VALUES (:id)'), {'id': b})
    app = portal_app()
    app.dependency_overrides[DBSessionDependency().dependency] = lambda: report_case.db
    # Keep API dependency composition real while using the fixture's ORM registry.
    for name in ('save_draft', 'retire', 'list_templates'):
        monkeypatch.setattr(PipelineTemplateService, name, getattr(env.template.PipelineTemplateService, name))
    actor = AsyncMock(return_value=current_user(a))
    monkeypatch.setattr(LoginService, 'get_current_user', actor)
    marker = 'tenant-http-' + uuid4().hex
    body = {
        'name': marker,
        'purpose': 'research',
        'reportType': 'research-demand',
        'prompt': '只使用所选资料',
        'userId': b,
    }
    headers = {'x-test-user': 'signed-in', 'Authorization': 'Bearer isolated-token'}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test', headers=headers
    ) as client:
        created = await client.post('/pipeline/templates', json=body)
        assert created.status_code == 200
        template_id = created.json()['data']['id']
        assert (await env.repo.ResearchDao.get_template(report_case.db, template_id)).user_id == a
        actor.return_value = current_user(b)
        for path in ('/pipeline/templates', '/pipeline/templates/published?category=research'):
            rows = (await client.get(path)).json()['data']['rows']
            assert template_id not in {row['id'] for row in rows}
        for method in ('PUT', 'DELETE'):
            with pytest.raises(env.exc):
                await client.request(method, f'/pipeline/templates/{template_id}', json={**body, 'name': '越权修改'})
        assert await env.template.PipelineTemplateService.get_published(report_case.db, template_id, b) is None
        actor.return_value = current_user(a)
        assert (
            await client.put(f'/pipeline/templates/{template_id}', json={**body, 'prompt': '本人修改已保存'})
        ).status_code == 200
        await client.delete(f'/pipeline/templates/{template_id}')
        rows = (await client.get('/pipeline/templates/published')).json()['data']['rows']
        assert template_id not in {row['id'] for row in rows}
        assert (await env.repo.ResearchDao.get_template(report_case.db, template_id)).prompt == '本人修改已保存'
