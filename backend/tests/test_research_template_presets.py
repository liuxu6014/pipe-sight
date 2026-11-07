"""Concrete templates stay distinct, manually configurable and non-destructive."""

import importlib.util
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_no_external_network
from test_research_simplified_20261025 import payload, queue, seed

spec = importlib.util.spec_from_file_location(
    'research_template_presets', Path(__file__).parents[1] / 'scripts/bootstrap/seed_research_templates.py'
)
presets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(presets)
env = refactor_env
db = refactor_db
no_external_network = refactor_no_external_network


def test_each_type_has_three_different_purpose_specific_presets() -> None:
    rows = presets.load_presets()
    assert len(rows) == 9
    assert len({row['name'] for row in rows}) == 9
    for kind in presets.REPORT_TYPES:
        subset = [row for row in rows if row['report_type'] == kind]
        assert len(subset) == 3
        assert len({row['prompt'] for row in subset}) == 3
        assert len({tuple(section['title'] for section in row['sections']) for row in subset}) == 3
        assert all(len(row['sections']) >= 6 for row in subset)
        assert all(row['is_enabled'] and not row['image_config']['enabled'] for row in subset)


def test_installation_is_append_only_repeatable_and_keeps_admin_edits(env, db) -> None:
    original, _ = seed(env, db, model=False)
    table = env.configuration.PipelineTemplateVersion.__table__
    rows = presets.load_presets()
    conn = db.s.connection()
    preview = presets.install_presets(conn, table, rows)
    assert len(preview['pending']) == 9 and not preview['created']
    assert len(conn.execute(select(table)).all()) == 1
    result = presets.install_presets(conn, table, rows, apply=True)
    assert len(result['created']) == 9
    db.s.commit()
    assert original.prompt == '只使用资料' and original.model_id is None
    custom = db.s.get(env.configuration.PipelineTemplateVersion, int(result['created'][0]['id']))
    custom.prompt = '管理员自行修改的提示词'
    custom.sections = [{'id': 1, 'title': '定制章节', 'words': 500}]
    custom.is_enabled = False
    db.s.commit()
    before = deepcopy(custom.sections)
    again = presets.install_presets(db.s.connection(), table, rows, apply=True)
    db.s.commit()
    db.s.expire_all()
    assert again['created'] == [] and len(again['preserved']) == 9
    assert custom.prompt == '管理员自行修改的提示词' and custom.sections == before and not custom.is_enabled
    assert len(db.s.execute(select(table)).all()) == 10


@pytest.mark.asyncio
@pytest.mark.parametrize('preset', presets.load_presets(), ids=lambda row: row['name'])
async def test_each_new_template_queues_its_own_prompt_type_and_outline(env, db, preset, monkeypatch) -> None:
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    created = presets.install_presets(
        db.s.connection(), env.configuration.PipelineTemplateVersion.__table__, presets.load_presets(), apply=True
    )['created']
    db.s.commit()
    template_id = next(row['id'] for row in created if row['name'] == preset['name'])
    # Explicit model configuration keeps this fixture valid with either routing policy.
    chosen = db.s.get(env.configuration.PipelineTemplateVersion, int(template_id))
    chosen.model_id = 1
    db.s.commit()
    result = await queue(
        env,
        db,
        payload(
            template_id=template_id,
            report_type=preset['report_type'],
            requirements='按本次项目规范编制',
            outline=deepcopy(preset['sections']),
        ),
    )
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    snapshot = job.config_snapshot
    assert snapshot['template']['id'] == template_id
    assert snapshot['template']['report_type'] == preset['report_type']
    assert snapshot['template']['prompt'] == preset['prompt']
    assert snapshot['template']['sections'] == preset['sections']
    assert snapshot['request']['outline'] == preset['sections']
    assert snapshot['request']['requirements'] == '按本次项目规范编制'
