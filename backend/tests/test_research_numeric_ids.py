"""数字数据库 ID / 十进制字符串协议；内存库且禁止外部网络。"""

import importlib
from unittest.mock import AsyncMock

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import BigInteger, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_network
from test_research_simplified_20261025 import payload, queue, seed

env = refactor_env
db = refactor_db
no_external_network = refactor_network
LARGE_ID = 9007199254740993


def test_research_primary_keys_share_sequence_and_all_foreign_keys_are_bigint(env):
    for name in ('reports', 'generation_tasks', 'digest_schedules', 'report_assets', 'knowledge_files'):
        table = env.Base.metadata.tables[name]
        assert isinstance(table.c.id.type, BigInteger)
        assert table.c.id.default.name == 'business_id_seq'
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "nextval('business_id_seq')" in ddl
        for fk in table.foreign_keys:
            assert isinstance(fk.parent.type, BigInteger)
    assert env.models.PipelineResearchJob.__table__.c.request_id.type.length == 128
    assert env.models.PipelineResearchJob.__table__.c.execution_token.type.length == 64


@pytest.mark.parametrize(
    'invalid', ['report-old-uuid', '', '1.0', '1e3', '１２', 0, -1, True, 1.5, '9223372036854775808']
)
def test_http_id_fields_reject_legacy_or_lossy_identifiers(env, invalid):
    schema = importlib.import_module('app.intelligence.schemas.pipeline')
    with pytest.raises(ValidationError):
        TypeAdapter(schema.BusinessId).validate_python(invalid)
    with pytest.raises(ValidationError):
        schema.PipelineResearchJobCreateModel(**payload(template_id=invalid))
    with pytest.raises(ValidationError):
        schema.PipelineResearchJobCreateModel(
            **payload(materials=[{'type': 'file', 'id': invalid}], selected_item_ids=[])
        )


def test_http_dtos_preserve_bigint_precision_and_wire_strings(env):
    schema = importlib.import_module('app.intelligence.schemas.pipeline')
    dto = schema.PipelineResearchJobCreateModel(
        **payload(template_id=str(LARGE_ID), report_id=str(LARGE_ID + 1), selected_item_ids=[str(LARGE_ID + 2)])
    )
    assert dto.template_id == LARGE_ID and isinstance(dto.template_id, int)
    output = dto.model_dump(by_alias=True)
    assert output['templateId'] == str(LARGE_ID)
    assert output['reportId'] == str(LARGE_ID + 1)
    assert output['selectedItemIds'] == [str(LARGE_ID + 2)]


@pytest.mark.asyncio
async def test_repository_parses_before_sql_and_rejects_uuid_without_query(env, db, monkeypatch):
    _, material = seed(env, db)
    material.id = LARGE_ID
    await db.commit()
    statements = []
    original = db.scalar

    async def capture(query, *args, **kwargs):
        statements.append(query.compile().params)
        return await original(query, *args, **kwargs)

    monkeypatch.setattr(db, 'scalar', capture)
    assert await env.library_repo.MaterialDao.get_owned_material(db, str(LARGE_ID), 7) is material
    assert LARGE_ID in statements[0].values()
    assert str(LARGE_ID) not in statements[0].values()
    statements.clear()
    with pytest.raises(ValueError):
        await env.library_repo.MaterialDao.get_owned_material(db, 'doc-old-uuid', 7)
    with pytest.raises(ValueError):
        await env.repo.ResearchDao.get_report(db, 'report-old-uuid', 7)
    assert statements == []


@pytest.mark.asyncio
async def test_generated_relationships_are_int_and_snapshots_are_decimal_strings(env, db, monkeypatch):
    template, material = seed(env, db, image=True)
    template.image_config = {'enabled': True, 'prompt': '123 / doc-old-uuid 保留正文'}
    material.id = LARGE_ID
    material.edited_text = 'UUID-looking doc-old-uuid is ordinary content'
    await db.commit()
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    data = payload(
        request_id='request-old-uuid-token',
        selected_item_ids=[str(LARGE_ID)],
        requirements='123 / report-old-uuid 不替换',
    )
    result = await queue(env, db, data)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    assert isinstance(job.id, int) and job.report_id == report.id and isinstance(report.template_id, int)
    assert result['id'] == str(job.id) and result['reportId'] == str(report.id)
    snapshot = job.config_snapshot
    assert snapshot['template']['id'] == str(template.id)
    assert snapshot['template']['image_model_id'] == '2'
    assert snapshot['model']['id'] == '1' and snapshot['image_model']['id'] == '2'
    assert snapshot['request']['template_id'] == str(template.id)
    assert snapshot['request']['selected_item_ids'] == [{'type': 'file', 'id': str(LARGE_ID)}]
    assert snapshot['request']['requirements'] == data['requirements']
    assert job.request_id == 'manual:request-old-uuid-token'
    assert job.materials[0]['id'] == str(LARGE_ID)
    assert job.materials[0]['content'] == material.edited_text
    exports = importlib.import_module('app.research.services.exports')
    await exports.ResearchReportExportService.queue_images(db, job, report)
    await db.commit()
    asset = db.s.scalars(select(env.models.PipelineReportAsset)).one()
    assert isinstance(asset.id, int) and asset.task_id == job.id and asset.model_id == 2
    assert asset.config_snapshot['model']['id'] == '2'
    assert asset.prompt == template.image_config['prompt']


@pytest.mark.asyncio
async def test_report_history_and_resource_serializers_use_decimal_ids(env, db):
    seed(env, db)
    report = env.models.PipelineReport(
        id=LARGE_ID,
        user_id=7,
        title='真实报告',
        type='research',
        template_id=201,
        content='正文',
        version=1,
    )
    db.add(report)
    await db.commit()
    result = env.app.ResearchApplicationService.report_dict(report)
    assert result['id'] == str(LARGE_ID) and result['templateId'] == '201'
    assert (await env.materials.MaterialApiService.get_material(db, 7, '101'))['id'] == '101'
    execution = importlib.import_module('app.research.services.execution')
    await execution.ResearchExecutionService.save_version(db, report, 'manual', 7, '用户')
    versions = await env.app.ResearchApplicationService.list_report_versions(db, 7, str(LARGE_ID))
    assert versions['rows'][0]['reportId'] == str(LARGE_ID)
    assert versions['rows'][0]['id'].isdecimal()
    exports = importlib.import_module('app.research.services.exports')
    asset = await exports.ResearchReportExportService.create(db, user_id=7, report_id=str(LARGE_ID), file_format='pdf')
    assert asset['id'].isdecimal() and asset['reportId'] == str(LARGE_ID)


@pytest.mark.asyncio
async def test_schedule_snapshots_normalize_only_typed_entity_references(env, db):
    template, _ = seed(env, db, model=False)
    template.purpose = 'digest'
    template.name = '通用简报模板'
    await db.commit()
    data = {
        'name': '周期',
        'report_type': 'daily',
        'template_id': '201',
        'enabled': False,
        'selection_config': {'source_ids': [LARGE_ID], 'category_ids': ['801'], 'keywords': ['123', 'doc-old-uuid']},
        'generation_config': {'requirements': '123 UUID原样'},
    }
    result = await env.schedules.DigestScheduleService.create(
        db, user_id=7, owner_name='用户', payload=data, template_service=env.template.PipelineTemplateService
    )
    row = await env.repo.ResearchDao.lock_digest_schedule_for_update(db, result['id'], 7)
    assert isinstance(row.id, int) and row.template_id == 201
    assert result['id'] == str(row.id) and result['templateId'] == '201'
    assert row.selection_config == {
        'source_ids': [str(LARGE_ID)],
        'category_ids': ['801'],
        'keywords': ['123', 'doc-old-uuid'],
    }
    assert row.generation_config == {'requirements': '123 UUID原样'}
    assert not row.is_enabled and row.next_run_at is None


def test_manuscript_ids_use_the_same_strict_wire_protocol(env):
    schema = importlib.import_module('app.research.schemas.manuscript')
    dto = schema.ManuscriptGenerateModel(topic='题目', templateId=str(LARGE_ID), selectedItemIds=['101'])
    assert dto.template_id == LARGE_ID
    assert dto.model_dump(by_alias=True)['templateId'] == str(LARGE_ID)
    with pytest.raises(ValidationError):
        schema.ManuscriptGenerateModel(topic='题目', templateId='old-uuid')
