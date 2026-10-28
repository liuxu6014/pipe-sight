"""离线验证：只用内存 SQLite；隔离跨域旧 __init__，禁止外部连接。"""

import importlib
import sys
import types
from contextlib import contextmanager
from datetime import datetime, time, timezone
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import BigInteger, Column, Table, create_engine, event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.schema import CreateTable


@contextmanager
def raises(env, message):
    with pytest.raises(env.exc) as caught:
        yield
    assert message in caught.value.message


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    import socket

    def blocked(*args, **kwargs):
        raise AssertionError('offline test attempted external network')

    monkeypatch.setattr(socket.socket, 'connect', blocked)


@pytest.fixture(scope='module')
def env():
    root = Path(__file__).resolve().parents[1]
    before = dict(sys.modules)
    for key in list(sys.modules):
        if key.startswith(
            (
                'app.research',
                'app.business_ids',
                'app.library',
                'app.intelligence.models',
                'app.intelligence.services.templates',
                'app.intelligence.services.ai_model_service',
                'app.intelligence.schemas.ai_model',
                'app.infrastructure.services.secret_crypto',
                'app.system.services.file_scan',
            )
        ):
            del sys.modules[key]
    sys.path[:0] = [str(root / 'src'), str(root)]

    class Base(DeclarativeBase):
        pass

    database = types.ModuleType('config.database')
    database.Base = Base
    database.AsyncSessionLocal = None
    sys.modules['config.database'] = database
    # 配置替身不读真实 env，不创建数据库或 Redis 引擎。
    cfg = types.ModuleType('config.env')
    cfg.UploadConfig = NS(
        UPLOAD_PATH='/tmp/offline-research-upload',
        UPLOAD_PREFIX='/profile',
        MAX_UPLOAD_BYTES=16 * 1024 * 1024,
        FILE_SCAN_MODE='basic',
        FILE_SCAN_COMMAND='',
        FILE_SCAN_TIMEOUT_SECONDS=1,
    )
    cfg.JwtConfig = NS(jwt_secret_key='offline-test-key')
    sys.modules['config.env'] = cfg
    package = types.ModuleType('app.intelligence.models')
    package.__path__ = [str(root / 'src/app/intelligence/models')]
    sys.modules['app.intelligence.models'] = package
    # 日志替身避免加载应用生命周期。
    log = types.ModuleType('app.infrastructure.services.logging_support')
    log.logger = NS(exception=lambda *a, **k: None, warning=lambda *a, **k: None, info=lambda *a, **k: None)
    sys.modules[log.__name__] = log
    models = importlib.import_module('app.research.models.research_models')
    material = importlib.import_module('app.library.models.materials')
    configuration = importlib.import_module('app.intelligence.models.configuration')
    ai = importlib.import_module('app.intelligence.models.ai_models')
    repo = importlib.import_module('app.research.repositories.research_repository')
    library_repo = importlib.import_module('app.library.repositories.material_repository')
    app = importlib.import_module('app.research.services.application')
    template = importlib.import_module('app.intelligence.services.templates')
    materials = importlib.import_module('app.library.services.materials')
    gateway = importlib.import_module('app.research.services.model_generation')
    schedules = importlib.import_module('app.research.services.digest_schedules')
    ai_service = importlib.import_module('app.intelligence.services.ai_model_service')
    ai_schema = importlib.import_module('app.intelligence.schemas.ai_model')
    exc = importlib.import_module('exceptions.exception').ServiceException
    # 只提供 FK 目标；不是兼容视图或业务模型替身。
    for name in ('sys_user', 'news_articles', 'papers'):
        if name not in Base.metadata.tables:
            Table(name, Base.metadata, Column('id', BigInteger, primary_key=True))
    # SQLite 不支持 bigint 自增，测试端使用 variant 保持生产 PostgreSQL bigint。
    for table in (
        models.PipelineReportVersion.__table__,
        models.PipelineWorkspaceItem.__table__,
        ai.AiModels.__table__,
    ):
        from sqlalchemy import Integer

        table.c.id.type = BigInteger().with_variant(Integer(), 'sqlite')
    yield NS(**locals())
    for key in list(sys.modules):
        if key not in before and (
            key.startswith('app.')
            or key.startswith('config.')
            or key.startswith('common.')
            or key.startswith('exceptions.')
        ):
            del sys.modules[key]
    for key, value in before.items():
        sys.modules[key] = value
    for key, value in before.items():
        if key.startswith(('app.', 'config.', 'common.', 'exceptions.')) and '.' in key:
            parent, attribute = key.rsplit('.', 1)
            if parent in before:
                setattr(before[parent], attribute, value)
    sys.path.remove(str(root / 'src'))
    sys.path.remove(str(root))


class AsyncMemory:
    """将真实同步 SQLite Session 包装成服务需要的异步接口。"""

    def __init__(self, session):
        self.s = session

    async def scalar(self, *a, **k):
        return self.s.scalar(*a, **k)

    async def scalars(self, *a, **k):
        return self.s.scalars(*a, **k)

    async def execute(self, *a, **k):
        return self.s.execute(*a, **k)

    async def get(self, *a, **k):
        return self.s.get(*a, **k)

    def add(self, item):
        self.s.add(item)

    async def flush(self):
        self.s.flush()

    async def commit(self):
        self.s.commit()

    async def rollback(self):
        self.s.rollback()

    async def refresh(self, item):
        self.s.refresh(item)

    async def delete(self, item):
        self.s.delete(item)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        if args[0]:
            self.s.rollback()
        self.s.close()


@pytest.fixture
def db(env):
    engine = create_engine('sqlite:///:memory:')

    @event.listens_for(engine, 'connect')
    def foreign_keys(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')

    env.Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    session.execute(env.Base.metadata.tables['sys_user'].insert().values(id=7))
    session.execute(env.Base.metadata.tables['sys_user'].insert().values(id=8))
    session.commit()
    yield AsyncMemory(session)
    session.close()
    engine.dispose()


def seed(env, db, *, model=True, image=False):
    if model:
        db.add(
            env.ai.AiModels(
                id=1,
                name='文字',
                provider='openai-compatible',
                code='text',
                base_url='https://offline.invalid/v1',
                credential_ref='env:OFFLINE_MODEL_KEY',
                capabilities=['text_generate'],
                parameters={},
                is_enabled=True,
            )
        )
    if image:
        db.add(
            env.ai.AiModels(
                id=2,
                name='图片',
                provider='openai-compatible',
                code='image',
                base_url='https://offline.invalid/v1',
                credential_ref='env:OFFLINE_MODEL_KEY',
                capabilities=['image_generate'],
                parameters={},
                is_enabled=True,
            )
        )
    db.s.flush()
    template = env.configuration.PipelineTemplateVersion(
        id=201,
        name='模板',
        purpose='research',
        prompt='只使用资料',
        model_id=1 if model else None,
        image_model_id=2 if image else None,
        sections=[],
        image_config={},
        is_enabled=True,
    )
    db.add(template)
    file = env.material.PipelineMaterial(
        id=101,
        user_id=7,
        name='资料',
        filename='a.txt',
        storage_key='a.txt',
        mime_type='text/plain',
        size=1,
        hash='a' * 64,
        status='ready',
        extracted_text='原提取文本',
        edited_text=None,
        version=1,
    )
    db.add(file)
    db.s.commit()
    return template, file


def payload(**updates):
    return {
        'title': '测试报告',
        'report_type': 'research',
        'template_id': '201',
        'selected_item_ids': ['101'],
        'request_id': 'same',
        'options': {},
        **updates,
    }


async def queue(env, db, data=None, user_id=7):
    return await env.app.ResearchApplicationService.queue_job(
        db, user_id=user_id, owner_name='测试', payload=data or payload()
    )


def test_exact_columns_and_composite_fk(env):
    assert set(env.models.PipelineReport.__table__.c.keys()) == set(
        'id user_id title type template_id content version created_at updated_at'.split()
    )
    job = env.models.PipelineResearchJob.__table__
    assert 'user_id' not in job.c and 'materials' in job.c
    assert set(env.material.PipelineMaterial.__table__.c.keys()) == set(
        'id user_id name filename storage_key mime_type size hash extracted_text edited_text version status error created_at updated_at'.split()
    )
    assert env.configuration.PipelineTemplateVersion.__table__.c.model_id.nullable
    asset = env.models.PipelineReportAsset.__table__
    assert asset.name == 'report_assets' and 'format' not in asset.c and 'user_id' not in asset.c
    foreign = [fk for fk in asset.foreign_key_constraints if 'task_id' in fk.column_keys]
    assert len(foreign) == 1 and foreign[0].column_keys == ['task_id', 'report_id']
    assert 'jsonb_array_length' in str(CreateTable(job).compile(dialect=postgresql.dialect()))
    assert not {'report_exports', 'report_publications', 'model_routes', 'template_versions'} & set(
        env.Base.metadata.tables
    )


def test_business_user_foreign_keys_reference_original_ruoyi_table_with_canonical_id(env):
    for table_name, column_name, ondelete in (
        ('knowledge_files', 'user_id', 'RESTRICT'),
        ('reports', 'user_id', 'RESTRICT'),
        ('digest_schedules', 'user_id', 'RESTRICT'),
        ('basket_items', 'user_id', 'CASCADE'),
        ('report_versions', 'operator_id', 'SET NULL'),
    ):
        table = env.Base.metadata.tables[table_name]
        (fk,) = table.c[column_name].foreign_keys
        assert fk.target_fullname == 'sys_user.id' and fk.ondelete == ondelete
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert f'FOREIGN KEY({column_name}) REFERENCES sys_user (id)' in ddl
        assert 'REFERENCES users ' not in ddl
    assert 'users' not in env.Base.metadata.tables


@pytest.mark.asyncio
async def test_no_model_browse_and_selection_but_submit_fails(env, db):
    seed(env, db, model=False)
    result = await env.template.PipelineTemplateService.list_templates(db)
    assert result['total'] == 1 and result['rows'][0]['modelId'] is None
    assert await env.template.PipelineTemplateService.get_published(db, '201')
    with raises(env, 'text_generate'):
        await queue(env, db)
    assert not db.s.scalars(select(env.models.PipelineReport)).all()


@pytest.mark.asyncio
async def test_freeze_idempotency_and_cross_user_rejection(env, db, monkeypatch):
    _, file = seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    file.extracted_text = '后来的正文'
    db.s.commit()
    assert job.materials[0]['content'] == '原提取文本'
    assert job.materials[0]['type'] == 'file'
    assert '原提取文本' not in str(job.config_snapshot)
    assert (await queue(env, db))['reused']
    with raises(env, '幂等键'):
        await queue(env, db, user_id=8)
    with raises(env, '幂等键'):
        await queue(env, db, payload(title='另一个标题'))
    assert len(db.s.scalars(select(env.models.PipelineReport)).all()) == 1


@pytest.mark.asyncio
async def test_empty_edit_does_not_fallback_and_over_limit_fails(env, db, monkeypatch):
    _, file = seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    file.edited_text = ''
    db.s.commit()
    with raises(env, '正文为空'):
        await queue(env, db)
    with raises(env, '50'):
        await queue(env, db, payload(selected_item_ids=['101'] * 51))


@pytest.mark.asyncio
async def test_context_budget_and_duplicate_rejection(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    with raises(env, '重复'):
        await queue(env, db, payload(selected_item_ids=['101', '101']))
    model = await db.get(env.ai.AiModels, 1)
    model.parameters = {'context_chars': 1}
    db.s.commit()
    with raises(env, '上下文'):
        await queue(env, db)


@pytest.mark.asyncio
async def test_image_input_is_not_image_generation(env, db, monkeypatch):
    template, _ = seed(env, db, image=True)
    model = await db.get(env.ai.AiModels, 2)
    model.capabilities = ['image_input']
    template.image_config = {'enabled': True}
    db.s.commit()
    with raises(env, 'image_generate'):
        await queue(env, db)


@pytest.mark.asyncio
async def test_parse_cas_preserves_user_edits(env, db):
    _, file = seed(env, db)
    file.status = 'queued'
    file.edited_text = '我的编辑'
    db.s.commit()
    claimed = await env.library_repo.MaterialDao.claim_material_parse(db, '101')
    token = claimed._parse_token
    assert await env.library_repo.MaterialDao.finish_material_parse(
        db, '101', parse_token=token, status='ready', extracted_text='新提取'
    )
    db.s.expire_all()
    row = await db.get(env.material.PipelineMaterial, 101)
    assert row.edited_text == '我的编辑' and row.extracted_text == '新提取' and row.version == 1
    assert not await env.library_repo.MaterialDao.finish_material_parse(
        db, '101', parse_token=token, status='ready', extracted_text='过期结果'
    )


@pytest.mark.asyncio
async def test_material_editor_persists_revision_without_replacing_source_file(env, db):
    _, material = seed(env, db)
    await db.commit()
    original_text, original_key, original_filename = material.extracted_text, material.storage_key, material.filename
    result = await env.materials.MaterialApiService.edit(
        db, 7, '101', expected_version=1, edited_text='人工修订的研究资料正文', name='修订资料.txt'
    )
    assert result['name'] == '修订资料.txt' and result['versionNo'] == 2
    assert result['content'] == '人工修订的研究资料正文'
    reread = await env.materials.MaterialApiService.get_material(db, 7, '101')
    assert reread['editedText'] == result['content'] and reread['summary']
    assert material.extracted_text == original_text and material.storage_key == original_key
    assert material.filename == original_filename
    with raises(env, '版本已变化'):
        await env.materials.MaterialApiService.edit(db, 7, '101', expected_version=1, edited_text='过期修改')
    with raises(env, '无权访问'):
        await env.materials.MaterialApiService.edit(db, 8, '101', expected_version=2, edited_text='其他用户')
    assert material.edited_text == '人工修订的研究资料正文' and material.version == 2


@pytest.mark.asyncio
async def test_report_read_scope_is_consistent_without_granting_writes(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    report_id = result['reportId']
    report = await env.repo.ResearchDao.get_report(db, report_id, 7)
    execution = importlib.import_module('app.research.services.execution')
    await execution.ResearchExecutionService.save_version(db, report, 'manual', 7, 'owner')
    service = env.app.ResearchApplicationService
    assert not (await service.get_report(db, 7, report_id))['readOnly']
    for read in (
        lambda: service.get_report(db, 8, report_id),
        lambda: service.list_report_versions(db, 8, report_id),
        lambda: service.get_report_version(db, 8, report_id, 1),
        lambda: service.list_report_exports(db, 8, report_id),
    ):
        with raises(env, '无权访问'):
            await read()
    assert (await service.get_report(db, 8, report_id, include_all=True))['readOnly']
    assert (await service.list_report_versions(db, 8, report_id, include_all=True))['total'] == 1
    assert (await service.get_report_version(db, 8, report_id, 1, include_all=True))['versionNo'] == 1
    assert (await service.list_report_exports(db, 8, report_id, include_all=True))['total'] == 0
    with raises(env, '无权访问'):
        await service.update_report(db, user_id=8, owner_name='other', report_id=report_id,
                                    payload=NS(expected_version=1, content='unauthorized'))
    with raises(env, '无权访问'):
        await service.restore_report_version(db, user_id=8, owner_name='other', report_id=report_id, version_no=1)
    with raises(env, '无权访问'):
        await service.create_report_export(db, 8, report_id, 'pdf')


@pytest.mark.asyncio
async def test_save_restore_and_optimistic_lock(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    report_id = result['reportId']
    update = NS(expected_version=1, expected_revision=None, content='用户内容', title='新标题')
    saved = await env.app.ResearchApplicationService.update_report(
        db, user_id=7, owner_name='测试', report_id=report_id, payload=update
    )
    assert saved['versionNo'] == 2 and saved['content'] == '用户内容'
    with raises(env, '版本'):
        await env.app.ResearchApplicationService.update_report(
            db, user_id=7, owner_name='测试', report_id=report_id, payload=update
        )
    restored = await env.app.ResearchApplicationService.restore_report_version(
        db, user_id=7, owner_name='测试', report_id=report_id, version_no=1
    )
    assert restored['versionNo'] == 3 and restored['content'] == ''
    assert len((await env.app.ResearchApplicationService.list_report_versions(db, 7, report_id))['rows']) == 3


@pytest.mark.asyncio
async def test_token_fencing_and_cancel_preserve_report(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.claim_research_job(db, result['jobId'], 7)
    token = job.execution_token
    assert await env.repo.ResearchDao.lock_running_research_job(db, job.id, 7, token)
    assert not await env.repo.ResearchDao.lock_running_research_job(db, job.id, 7, 'stale')
    await env.app.ResearchApplicationService.cancel_job(db, 7, job.id)
    assert not await env.repo.ResearchDao.lock_running_research_job(db, job.id, 7, token)
    assert await env.repo.ResearchDao.get_report(db, result['reportId'], 7)


def test_short_month_and_timezone(env):
    row = env.models.PipelineDigestSchedule(
        frequency='monthly', month_day=31, weekday=None, timezone='Asia/Shanghai', run_time=time(8), selection_config={}
    )
    start = datetime(2026, 1, 31, 1, tzinfo=timezone.utc)
    assert env.schedules.DigestScheduleService.next_run(row, start) == datetime(2026, 2, 28, 0, tzinfo=timezone.utc)
    start = datetime(2026, 2, 28, 1, tzinfo=timezone.utc)
    assert env.schedules.DigestScheduleService.next_run(row, start) == datetime(2026, 3, 31, 0, tzinfo=timezone.utc)
    row.frequency = 'daily'
    row.month_day = None
    row.run_time = time(8, 0, 30)
    assert env.schedules.DigestScheduleService.next_run(
        row, datetime(2026, 3, 1, 0, 0, 15, tzinfo=timezone.utc)
    ) == datetime(2026, 3, 1, 0, 0, 30, tzinfo=timezone.utc)


def test_legacy_model_dto_does_not_infer_image_generation(env):
    dto = env.ai_schema.AiModelModel(modelId=3, modelName='文本', modelCode='x', modelType='text', supportImages='Y')
    assert dto.id == 3 and dto.capabilities == ['text_generate', 'image_input']
    assert 'image_generate' not in dto.capabilities


@pytest.mark.asyncio
async def test_model_crud_uses_new_columns_and_hides_credentials(env, db):
    dto = env.ai_schema.AiModelModel(
        name='图片',
        provider='openai-compatible',
        code='image',
        baseUrl='https://offline.invalid/v1',
        credentialRef='env:OFFLINE_MODEL_KEY',
        capabilities=['image_generate'],
        parameters={},
        isEnabled=True,
    )
    await env.ai_service.AiModelService.add_ai_model_services(db, dto)
    result = await env.ai_service.AiModelService.get_ai_model_list_services(db, env.ai_schema.AiModelPageQueryModel())
    assert result[0]['capabilities'] == ['image_generate'] and result[0]['credentialRef'] is None
    assert 'OFFLINE_MODEL_KEY' not in str(result)


@pytest.mark.asyncio
async def test_gateway_missing_credential_fails_before_network(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.delenv('OFFLINE_MODEL_KEY', raising=False)
    with raises(env, '凭证'):
        await env.gateway.ModelGateway.call(
            db,
            {
                'id': 1,
                'code': 'text',
                'provider': 'openai-compatible',
                'base_url': 'https://offline.invalid/v1',
                'parameters': {},
            },
            capability='text_generate',
            prompt='x',
        )


@pytest.mark.asyncio
async def test_template_without_model_can_be_saved(env, db):
    row = await env.template.PipelineTemplateService.save_draft(
        db,
        template_key=None,
        operator_id=7,
        operator_name='管理员',
        payload={'purpose': 'research', 'name': '待配置', 'prompt': '真实提示词', 'sections': [], 'model_id': None},
    )
    assert row['modelId'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('conflict', [False, True])
async def test_execution_uses_frozen_input_and_retains_conflict_result(env, db, monkeypatch, conflict):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    execution = importlib.import_module('app.research.services.execution')

    def factory():
        return AsyncMemory(Session(db.s.bind, expire_on_commit=False))

    monkeypatch.setattr(execution, 'AsyncSessionLocal', factory)

    async def offline_model(model_db, snapshot, materials, **kwargs):
        assert materials[0]['content'] == '原提取文本'
        if conflict:
            async with factory() as edit_db:
                report = await env.repo.ResearchDao.get_report(edit_db, result['reportId'], 7)
                report.content = '编辑中的正文'
                report.version += 1
                await edit_db.commit()
        return '离线替身结果，未调用真实模型[1]。'

    monkeypatch.setattr(execution.ResearchModelGenerationService, 'generate_content', offline_model)
    await execution.ResearchExecutionService.process(job_id=result['jobId'], user_id=7)
    db.s.expire_all()
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    assert job.status == 'completed' and job.result_content.startswith('离线替身')
    from app.research.services.report_content import normalize_generated_report
    assert report.content == ('编辑中的正文' if conflict else normalize_generated_report(job.result_content, job.materials, delivery=True)['content'])
    if conflict:
        await env.app.ResearchReportService.apply_task_result(
            db,
            user_id=7,
            owner_name='用户',
            job_id=job.id,
            expected_version=report.version,
            report_serializer=env.app.ResearchApplicationService.report_dict,
        )
        assert report.content == normalize_generated_report(job.result_content, job.materials, delivery=True)['content']
        assert report.version == 3


@pytest.mark.asyncio
async def test_image_queue_and_export_download_permissions(env, db, monkeypatch):
    template, _ = seed(env, db, image=True)
    template.image_config = {'enabled': True, 'count': 2, 'prompt': '真实管道示意图'}
    db.s.commit()
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    exports = importlib.import_module('app.research.services.exports')
    await exports.ResearchReportExportService.queue_images(db, job, report)
    await db.commit()
    rows = await env.repo.ResearchDao.list_assets(db, report.id, 'image')
    assert len(rows) == 2 and all(row.model_id == 2 and row.task_id == job.id for row in rows)
    assert not await env.repo.ResearchDao.get_asset(db, rows[0].id, 8)
    rows[0].status = 'failed'
    await db.commit()
    assert (await exports.ResearchReportExportService.retry(db, 7, rows[0].id))['status'] == 'queued'
    with raises(env, '无权'):
        await exports.ResearchReportExportService.download(db, user_id=8, export_id=rows[0].id)


@pytest.mark.asyncio
async def test_asset_task_report_mismatch_is_rejected(env, db, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    first = await queue(env, db)
    second = await queue(env, db, payload(request_id='second'))
    bad = env.models.PipelineReportAsset(
        id=901,
        report_id=int(first['reportId']),
        task_id=int(second['jobId']),
        type='export',
        mime_type='application/pdf',
        config_snapshot={},
        status='queued',
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_model_pagination_and_edit_aliases(env, db):
    seed(env, db)
    page = await env.ai_service.AiModelService.get_ai_model_list_services(
        db, env.ai_schema.AiModelPageQueryModel(), is_page=True
    )
    assert page.total == 1
    dto = env.ai_schema.AiModelModel(modelId=1, modelName='新名称', status='1')
    await env.ai_service.AiModelService.edit_ai_model_services(db, dto)
    row = await db.get(env.ai.AiModels, 1)
    assert row.name == '新名称' and not row.is_enabled and row.credential_ref == 'env:OFFLINE_MODEL_KEY'


@pytest.mark.asyncio
async def test_parser_ready_and_file_type_detection(env, tmp_path):
    path = tmp_path / 'example.txt'
    path.write_text('有效的真实文本', encoding='utf-8')
    status, _, text, _ = env.materials.MaterialFileService.parse(str(path), 'example.txt', requested_at='offline')
    assert status == 'ready' and text == '有效的真实文本'
    assert env.materials.MaterialService.detect_mime(path, 'example.txt') == 'text/plain'
    path.write_bytes(b'MZfake executable')
    with raises(env, '类型'):
        env.materials.MaterialService.detect_mime(path, 'example.txt')


@pytest.mark.asyncio
async def test_image_gateway_decodes_actual_image_with_offline_transport(env, db, monkeypatch):
    import base64
    from io import BytesIO

    import httpx
    from PIL import Image

    seed(env, db, image=True)
    png = BytesIO()
    Image.new('RGB', (4, 4), 'blue').save(png, format='PNG')
    real_client = httpx.AsyncClient
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(png.getvalue()).decode()}]})

    monkeypatch.setenv('OFFLINE_MODEL_KEY', 'offline-placeholder-only')
    monkeypatch.setattr(
        env.gateway.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs)
    )
    result = await env.gateway.ModelGateway.call(
        db,
        {
            'id': 2,
            'code': 'image',
            'provider': 'openai-compatible',
            'base_url': 'https://offline.invalid/v1',
            'parameters': {},
        },
        capability='image_generate',
        prompt='蓝色方块',
        request_id='asset-offline',
    )
    assert result == png.getvalue()
    audits = list(db.s.scalars(select(env.configuration.PipelineModelCallAudit)))
    assert len(audits) == 1 and audits[0].capability == 'image_generate' and audits[0].status == 'success'
    assert audits[0].input_tokens is None and audits[0].error is None
    assert (
        requests[0].url.path == '/v1/images/generations' and requests[0].headers['Idempotency-Key'] == 'asset-offline'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('failed', [False, True])
async def test_model_call_audit_usage_and_safe_failure(env, db, monkeypatch, failed):
    import httpx

    seed(env, db)
    real_client = httpx.AsyncClient

    def respond(request):
        if failed:
            return httpx.Response(502, text='sensitive provider message must not persist')
        return httpx.Response(
            200,
            json={
                'choices': [{'message': {'content': '离线响应'}}],
                'usage': {'prompt_tokens': 11, 'completion_tokens': 7},
            },
        )

    monkeypatch.setenv('OFFLINE_MODEL_KEY', 'offline-not-a-real-key')
    monkeypatch.setattr(
        env.gateway.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs)
    )
    snapshot = {
        'id': 1,
        'code': 'text',
        'provider': 'openai-compatible',
        'base_url': 'https://offline.invalid/v1',
        'parameters': {},
    }
    if failed:
        with raises(env, '模型调用失败'):
            await env.gateway.ModelGateway.call(db, snapshot, capability='text_generate', prompt='不应记录的原文')
    else:
        assert (
            await env.gateway.ModelGateway.call(db, snapshot, capability='text_generate', prompt='不应记录的原文')
            == '离线响应'
        )
    await db.commit()
    audit = db.s.scalars(select(env.configuration.PipelineModelCallAudit)).one()
    assert audit.status == ('failed' if failed else 'success') and audit.duration_ms >= 0
    assert audit.input_tokens == (None if failed else 11) and audit.output_tokens == (None if failed else 7)
    assert 'sensitive' not in (audit.error or '')
    assert not {'prompt', 'content', 'api_key', 'credential_ref'} & set(audit.__table__.c.keys())


@pytest.mark.asyncio
async def test_paper_snapshot_only_contains_abstract(env, db, monkeypatch):
    paper = NS(
        id=501,
        title='原题',
        title_zh='中文题',
        abstract='原摘要',
        abstract_zh='译文摘要',
        doi='10.1/test',
        url='https://offline.invalid/p',
        journal='期刊',
        authors='作者',
        published_date='2024',
        content='禁止使用的全文',
    )

    async def content(db, kind, item_id):
        return paper if kind == 'paper' and item_id == 501 else None

    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', content)
    evidence = importlib.import_module('app.research.services.evidence')
    result = await evidence.ResearchEvidenceService.resolve(db, 7, [{'type': 'paper', 'id': '501'}])
    assert result[0]['content'] == '译文摘要' and result[0]['source']['published_date'] == '2024'
    assert '禁止使用的全文' not in str(result)


@pytest.mark.asyncio
async def test_private_material_cannot_be_selected_by_other_user(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    with raises(env, '无权'):
        await queue(env, db, payload(request_id='another-user'), user_id=8)
