"""Offline integration: isolated ORM registry + SQLite memory + fixed async adapter.

No application config, real engine, migration or crawler is imported. SQLite
checks row/unique/FK behavior; PostgreSQL FOR UPDATE concurrency is only compiled.
"""

import asyncio
import importlib
import socket
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.schema import CreateIndex, CreateTable

ROOT = Path(__file__).resolve().parents[2] / 'src' / 'app'
NOW = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)


class AsyncMemorySession:
    """Small async interface around an actual local SQLAlchemy Session."""

    def __init__(self, engine):
        self.sync = Session(engine, expire_on_commit=False, autoflush=False)

    async def execute(self, *args, **kwargs):
        return self.sync.execute(*args, **kwargs)

    async def get(self, *args, **kwargs):
        return self.sync.get(*args, **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.sync.close()

    async def commit(self):
        self.sync.commit()

    async def rollback(self):
        self.sync.rollback()

    async def flush(self):
        self.sync.flush()

    def add(self, value):
        self.sync.add(value)

    def get_bind(self):
        return self.sync.get_bind()

    @asynccontextmanager
    async def begin_nested(self):
        with self.sync.begin_nested():
            yield


@pytest.fixture
def env(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('外网/真实数据库连接被测试阻断')

    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    # Imports only files owned by this task, not the old model aggregation.
    for key in list(sys.modules):
        if key in {'app', 'app.business_ids'} or key.startswith('app.intelligence'):
            monkeypatch.delitem(sys.modules, key)
    for name, path in [('app', ROOT), ('app.intelligence', ROOT / 'intelligence')]:
        package = ModuleType(name)
        package.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, package)
    for name in ('models', 'repositories', 'services', 'schemas', 'tasks', 'integrations'):
        package = ModuleType(f'app.intelligence.{name}')
        package.__path__ = [str(ROOT / 'intelligence' / name)]
        monkeypatch.setitem(sys.modules, package.__name__, package)

    class Base(DeclarativeBase):
        pass

    database = ModuleType('config.database')
    database.Base = Base
    monkeypatch.setitem(sys.modules, 'config.database', database)
    model = importlib.import_module('app.intelligence.models.collection')
    business_pk = importlib.import_module('app.business_ids').business_pk

    # Content contract supplied by the main agent, intentionally no legacy fields.
    class AiModels(Base):
        __tablename__ = 'ai_models'
        id = Column(BigInteger, primary_key=True)
        provider = Column(Text)
        code = Column(Text)
        base_url = Column(Text)
        capabilities = Column(JSON)
        parameters = Column(JSON)
        is_enabled = Column(Boolean)

    models_module = ModuleType('app.intelligence.models.ai_models')
    models_module.AiModels = AiModels
    monkeypatch.setitem(sys.modules, models_module.__name__, models_module)

    def content_model(name, table, fields):
        attrs = {
            '__tablename__': table,
            'id': business_pk(),
            'source_id': Column(BigInteger, ForeignKey('data_sources.id')),
            'title': Column(String(1000), nullable=False),
            'url': Column(Text, unique=True),
            'category_id': Column(BigInteger),
            'is_pushed': Column(Boolean, nullable=False),
            'created_at': Column(DateTime(timezone=True)),
            'updated_at': Column(DateTime(timezone=True)),
        }
        attrs.update({name: Column(kind) for name, kind in fields.items()})
        return type(name, (Base,), attrs)

    content = ModuleType('app.intelligence.models.content')

    class PipelineCategory(Base):
        __tablename__ = 'categories'
        id = business_pk()
        name = Column(Text)
        prompt = Column(Text)
        model_id = Column(BigInteger, ForeignKey('ai_models.id'))
        applies_to = Column(Text)
        is_enabled = Column(Boolean)
        sort_order = Column(Integer)

    content.PipelineCategory = PipelineCategory
    content.PipelineArticle = content_model(
        'PipelineArticle',
        'news_articles',
        {'author': Text, 'published_at': DateTime(timezone=True), 'content': Text, 'content_zh': Text},
    )
    content.PipelinePaper = content_model(
        'PipelinePaper',
        'papers',
        {key: Text for key in ('title_zh', 'doi', 'authors', 'journal', 'published_date', 'abstract', 'abstract_zh')},
    )
    monkeypatch.setitem(sys.modules, content.__name__, content)
    repository = importlib.import_module('app.intelligence.repositories.collection_repository')
    collection = importlib.import_module('app.intelligence.services.collection')
    persistence = importlib.import_module('app.intelligence.services.collection_persistence')
    sources = importlib.import_module('app.intelligence.services.sources')
    state = SimpleNamespace(batches=[], calls=[], cleanup=False, category_requests=[], category_reply='{"match":true}')
    gateway = ModuleType('app.research.services.model_generation')

    class ModelGateway:
        @staticmethod
        async def call(db, snapshot, **kwargs):
            state.category_requests.append((snapshot, kwargs))
            if isinstance(state.category_reply, Exception):
                raise state.category_reply
            if callable(state.category_reply):
                return await state.category_reply(db)
            return state.category_reply

    gateway.ModelGateway = ModelGateway
    monkeypatch.setitem(sys.modules, gateway.__name__, gateway)
    engine = create_engine('sqlite:///:memory:')

    @event.listens_for(engine, 'connect')
    def fk_on(connection, _):
        connection.isolation_level = None
        connection.execute('PRAGMA foreign_keys=ON')

    @event.listens_for(engine, 'begin')
    def explicit_begin(connection):
        connection.exec_driver_sql('BEGIN')

    Base.metadata.create_all(engine)
    monkeypatch.setattr(collection, 'classification_session_factory', lambda db: lambda: AsyncMemorySession(engine))
    registry = collection.AdapterRegistry()

    async def fixed(snapshot, checkpoint):
        state.calls.append((snapshot, checkpoint))
        try:
            for batch in state.batches:
                if isinstance(batch, Exception):
                    raise batch
                if callable(batch):
                    batch = await batch()
                yield batch
        finally:
            state.cleanup = True

    registry.register('fixed', collection.Adapter(fixed, ('website', 'wechat', 'paper'), ('example.test',), True))
    db = AsyncMemorySession(engine)
    result = SimpleNamespace(
        db=db,
        engine=engine,
        models=model,
        content=content,
        ai_model=AiModels,
        repo=repository.CollectionRepository,
        conflict=repository.CollectionConflict,
        lost=repository.LeaseLost,
        service=sources.IntelligenceSourceService,
        sources=sources,
        collection=collection,
        persistence=persistence,
        registry=registry,
        state=state,
        clock=lambda: NOW,
        batch=collection.CollectionBatch,
    )
    yield result
    db.sync.close()
    engine.dispose()
    # Remove this fixture's imported modules; pytest monkeypatch restores originals.
    for key in list(sys.modules):
        if key.startswith('app.intelligence.') and key not in ('app.intelligence.models.content',):
            sys.modules.pop(key, None)


async def source(e, **kwargs):
    payload = {'name': '固定来源', 'type': 'website', 'url': 'https://example.test/feed', 'adapter': 'fixed'}
    payload.update(kwargs)
    return await e.service.save(e.db, **payload, registry=e.registry, clock=e.clock)


async def enqueue(e, source_id, request_id='manual:test'):
    return await e.service.queue_collection_run(
        e.db, source_id, request_id=request_id, registry=e.registry, clock=e.clock
    )


async def execute(e, run_id):
    return await e.collection.PipelineCollectionService.execute(e.db, run_id, registry=e.registry, clock=e.clock)


def test_exact_schema_and_postgres_constraints(env):
    e = env
    assert list(e.models.PipelineSource.__table__.columns.keys()) == [
        'id',
        'name',
        'type',
        'url',
        'adapter',
        'cron',
        'timezone',
        'next_run_at',
        'config',
        'model_id',
        'is_enabled',
        'created_at',
        'updated_at',
    ]
    assert list(e.models.PipelineCrawlRun.__table__.columns.keys()) == [
        'id',
        'source_id',
        'parent_id',
        'trigger_type',
        'request_id',
        'status',
        'available_at',
        'config_snapshot',
        'checkpoint',
        'fetched_count',
        'saved_count',
        'failed_count',
        'error',
        'stop_requested_at',
        'execution_token',
        'lease_expires_at',
        'started_at',
        'finished_at',
        'created_at',
        'updated_at',
    ]
    ddl = str(CreateTable(e.models.PipelineCrawlRun.__table__).compile(dialect=postgresql.dialect()))
    assert (
        'FOREIGN KEY(parent_id, source_id) REFERENCES collection_runs (id, source_id) MATCH SIMPLE ON DELETE RESTRICT'
        in ddl
    )
    assert 'JSONB' in ddl and 'TIMESTAMP WITH TIME ZONE' in ddl
    indexes = ' '.join(
        str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in e.models.PipelineCrawlRun.__table__.indexes
    )
    assert "WHERE status IN ('queued','running','stopping')" in indexes
    sql = str(select(e.models.PipelineSource).with_for_update().compile(dialect=postgresql.dialect()))
    assert sql.endswith('FOR UPDATE')


@pytest.mark.asyncio
async def test_manual_idempotency_active_exclusion_and_repeat_delivery(env):
    e = env
    s = await source(e)
    first = await enqueue(e, s['id'])
    assert (await enqueue(e, s['id']))['id'] == first['id']
    assert (await enqueue(e, s['id'], 'manual:other'))['id'] == first['id']
    assert (await execute(e, first['id']))['status'] == 'success'  # truthful empty source
    assert (await execute(e, first['id']))['status'] == 'skipped'
    assert (await enqueue(e, s['id']))['id'] == first['id']
    s2 = await source(e)
    with pytest.raises(e.conflict):
        await enqueue(e, s2['id'])
    assert len(e.state.calls) == 1


@pytest.mark.asyncio
async def test_disable_cancels_queue_and_enable_does_not_revive(env):
    e = env
    s = await source(e, cron='0 8 * * *')
    assert s['next_run_at']
    r = await enqueue(e, s['id'])
    disabled = await e.service.set_enabled(e.db, s['id'], False, registry=e.registry, clock=e.clock)
    assert disabled['next_run_at'] is None
    run = await e.repo.run(e.db, r['id'])
    assert run.status == 'cancelled' and run.stop_requested_at and run.finished_at and run.started_at is None
    with pytest.raises(e.conflict):
        await enqueue(e, s['id'], 'manual:new')
    await e.service.set_enabled(e.db, s['id'], True, registry=e.registry, clock=e.clock)
    assert (await execute(e, r['id']))['status'] == 'skipped'


@pytest.mark.asyncio
async def test_stopping_blocks_writes_and_waits_for_cleanup(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])

    async def stop_during_request():
        other = AsyncMemorySession(e.engine)
        stop = await e.service.stop_collection_run(other, r['id'], clock=e.clock)
        assert stop['status'] == 'stopping' and stop['finished_at'] is None
        assert stop['message'] == '已请求停止'
        assert (await e.service.stop_collection_run(other, r['id'], clock=e.clock))['stop_requested_at'] == stop[
            'stop_requested_at'
        ]
        other.sync.close()
        return e.batch([{'title': '不得写入', 'url': 'https://example.test/a'}], {'page': 1})

    e.state.batches = [stop_during_request]
    assert (await execute(e, r['id']))['status'] == 'cancelled'
    assert e.state.cleanup
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert (await e.service.stop_collection_run(e.db, r['id'], clock=e.clock))['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_disable_running_does_not_fake_stop(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    claimed = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=60)
    token = claimed.execution_token
    await e.service.set_enabled(e.db, s['id'], False, registry=e.registry, clock=e.clock)
    assert (await e.repo.run(e.db, r['id'])).status == 'running'
    assert (await e.repo.finish(e.db, r['id'], token, now=NOW)).status == 'success'


@pytest.mark.asyncio
async def test_retry_chain_frozen_snapshot_unique_child_and_backoff(env):
    e = env
    s = await source(e, config={'retry': {'enabled': True, 'max_retries': 2, 'backoff_seconds': 10}})
    r = await enqueue(e, s['id'])
    e.state.batches = [e.collection.TransientCollectionError('Cookie: SECRET')]
    assert (await execute(e, r['id']))['status'] == 'failed'
    parent = await e.repo.run(e.db, r['id'])
    assert 'SECRET' not in parent.error
    child = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    assert child['parent_id'] == r['id'] and child['available_at'] == (NOW + timedelta(seconds=10)).isoformat()
    assert (await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock))['id'] == child[
        'id'
    ]
    assert (await execute(e, child['id']))['status'] == 'skipped'
    await e.service.save(
        e.db,
        source_id=int(s['id']),
        name='已修改',
        type='website',
        adapter='fixed',
        config={'changed': True},
        registry=e.registry,
        clock=e.clock,
    )
    for index in range(2):
        time = NOW + timedelta(seconds=10 * (2 ** (index + 1) - 1))
        e.clock = lambda time=time: time
        assert (await execute(e, child['id']))['status'] == 'failed'
        parent = await e.repo.run(e.db, child['id'])
        assert parent.config_snapshot['config'] == s['config']
        child = await e.service.retry_collection_run(
            e.db, parent.id, automatic=True, registry=e.registry, clock=e.clock
        )
        if index == 0:
            assert child['available_at'] == (time + timedelta(seconds=20)).isoformat()
        else:
            assert child is None  # 2 extra attempts, no redundant attempts column


@pytest.mark.asyncio
async def test_cancelled_retry_child_stays_cancelled(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    e.state.batches = [e.collection.TransientCollectionError()]
    await execute(e, r['id'])
    child = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    await e.service.stop_collection_run(e.db, child['id'], clock=e.clock)
    repeat = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    assert repeat['id'] == child['id'] and repeat['status'] == 'cancelled'
    with pytest.raises(e.conflict):
        await e.service.retry_collection_run(e.db, child['id'], registry=e.registry, clock=e.clock)


@pytest.mark.asyncio
async def test_partial_failure_restarts_from_entry_without_losing_saved_articles(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    record = {
        'title': '真实固定测试标题',
        'url': 'https://EXAMPLE.test/a?utm_source=x#fragment',
        'content': '固定测试正文',
    }
    e.state.batches = [
        e.batch([record, {'title': '坏条目', 'url': 'bad'}], {'page': 2}),
        e.batch([{'title': '第二批', 'url': 'https://example.test/b'}], {'page': 3}),
    ]
    assert (await execute(e, r['id']))['status'] == 'failed'
    parent = await e.repo.run(e.db, r['id'])
    assert (parent.fetched_count, parent.saved_count, parent.failed_count, parent.checkpoint) == (3, 2, 1, {})
    child = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    e.clock = lambda: NOW + timedelta(seconds=30)
    e.state.batches = [e.batch([record], {'page': 2})]
    assert (await execute(e, child['id']))['status'] == 'success'
    assert e.state.calls[-1][1] == {}
    articles = e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert len(articles) == 2 and articles[0].published_at is None
    child_run = await e.repo.run(e.db, child['id'])
    assert (child_run.fetched_count, child_run.saved_count, child_run.failed_count) == (1, 0, 0)


@pytest.mark.asyncio
async def test_papers_store_metadata_abstract_only_and_allow_url_without_doi(env):
    e = env
    s = await source(e, type='paper')
    r = await enqueue(e, s['id'])
    e.state.batches = [
        e.batch(
            [
                {
                    'title': '论文',
                    'doi': 'https://doi.org/10.1234/ABC',
                    'published_date': '2024-06',
                    'abstract': '摘要',
                    'content': '不得保存的全文',
                },
                {'title': '仅 URL', 'url': 'https://example.test/p', 'abstract': None},
            ],
            {},
        )
    ]
    assert (await execute(e, r['id']))['status'] == 'success'
    papers = e.db.sync.scalars(select(e.content.PipelinePaper)).all()
    assert len(papers) == 2
    assert papers[0].doi == '10.1234/abc' and papers[0].published_date == '2024-06'
    assert papers[1].published_date is None
    assert not hasattr(papers[0], 'content')


@pytest.mark.asyncio
async def test_lease_fences_batch_and_recovery_does_not_confirm_unobserved_stop(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=10)
    token = run.execution_token
    await e.service.stop_collection_run(e.db, r['id'], clock=e.clock)
    stopped = await e.repo.recover(e.db, r['id'], now=NOW + timedelta(seconds=11))
    assert stopped.status == 'stopping' and stopped.execution_token is None and stopped.finished_at is None
    with pytest.raises(e.lost):
        await e.persistence.CollectionPersistenceService.save_batch(
            e.db, r['id'], token, [], {}, now=NOW + timedelta(seconds=11)
        )
    stopped = await e.repo.recover(e.db, r['id'], now=NOW + timedelta(seconds=12), isolated=True)
    assert stopped.status == 'cancelled'


@pytest.mark.asyncio
async def test_running_crash_failed_and_old_worker_cannot_finish(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=10)
    token = run.execution_token
    run = await e.repo.recover(e.db, r['id'], now=NOW + timedelta(seconds=11))
    assert run.status == 'failed' and run.error == '执行器租约过期'
    with pytest.raises(e.lost):
        await e.repo.finish(e.db, r['id'], token, now=NOW + timedelta(seconds=12))
    await e.db.rollback()


@pytest.mark.asyncio
async def test_scheduler_advances_once_and_skips_active_round(env):
    e = env
    s = await source(e, cron='* * * * *', timezone='UTC')
    e.clock = lambda: NOW + timedelta(minutes=1)
    run = await e.service.schedule_due_source(e.db, s['id'], registry=e.registry, clock=e.clock)
    assert run['request_id'] == f'schedule:{s["id"]}:{e.clock().isoformat()}'
    assert await e.service.schedule_due_source(e.db, s['id'], registry=e.registry, clock=e.clock) is None
    e.clock = lambda: NOW + timedelta(minutes=10)
    assert await e.service.schedule_due_source(e.db, s['id'], registry=e.registry, clock=e.clock) is None
    cursor = (await e.repo.source(e.db, s['id'])).next_run_at
    assert cursor.replace(tzinfo=timezone.utc) == NOW + timedelta(minutes=11)
    assert len(await e.repo.history(e.db)) == 1


@pytest.mark.parametrize(
    'change',
    [
        {'adapter': 'unregistered'},
        {'timezone': 'bad/timezone'},
        {'cron': '* * bad'},
        {'url': 'http://127.0.0.1/private'},
        {'config': {'cron': '* * * * *'}},
        {'config': {'headers': {'Cookie': 'SECRET'}}},
        {'config': {'request_timeout': 0}},
        {'config': {'retry': {'max_retries': -1}}},
    ],
)
@pytest.mark.asyncio
async def test_invalid_source_config_rejected(env, change):
    with pytest.raises(env.collection.ConfigurationError):
        await source(env, **change)


@pytest.mark.asyncio
async def test_fk_rejects_cross_source_retry_and_partial_unique_blocks_second_active(env):
    e = env
    s, s2 = await source(e), await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=10)
    await e.repo.finish(e.db, run.id, run.execution_token, now=NOW, error='临时采集故障或请求超时')
    bad = e.models.PipelineCrawlRun(
        id=900001,
        source_id=int(s2['id']),
        parent_id=int(r['id']),
        trigger_type='retry',
        request_id=900001,
        available_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    e.db.add(bad)
    with pytest.raises(IntegrityError):
        await e.db.commit()
    await e.db.rollback()
    await enqueue(e, s['id'], 'manual:new')
    duplicate = e.models.PipelineCrawlRun(
        id=900002,
        source_id=int(s['id']),
        trigger_type='manual',
        request_id=900002,
        available_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    e.db.add(duplicate)
    with pytest.raises(IntegrityError):
        await e.db.commit()
    await e.db.rollback()


@pytest.mark.parametrize('value', ['2024-02-30', '2024-13', '2024-1', 'not-a-date'])
def test_paper_partial_date_rejects_fabricated_or_invalid_dates(env, value):
    with pytest.raises(ValueError):
        env.persistence.publication_date(value)


@pytest.mark.asyncio
async def test_batch_and_counters_rollback_together(env, monkeypatch):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=60)
    token = run.execution_token

    async def failed_commit():
        raise RuntimeError('模拟提交故障')

    monkeypatch.setattr(e.db, 'commit', failed_commit)
    with pytest.raises(RuntimeError):
        await e.persistence.CollectionPersistenceService.save_batch(
            e.db,
            run.id,
            token,
            [{'title': '事务测试', 'url': 'https://example.test/rollback'}],
            {'page': 1},
            now=NOW,
            supports_resume=True,
            clock=e.clock,
        )
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    run = await e.repo.run(e.db, r['id'])
    assert (run.fetched_count, run.saved_count, run.checkpoint) == (0, 0, {})


@pytest.mark.asyncio
async def test_request_timeout_cancels_adapter_and_default_no_auto_retry(env):
    e = env
    s = await source(e, config={'request_timeout': 0.01})
    r = await enqueue(e, s['id'])

    async def stalled():
        await asyncio.Event().wait()

    e.state.batches = [stalled]
    assert (await execute(e, r['id']))['status'] == 'failed'
    assert e.state.cleanup
    run = await e.repo.run(e.db, r['id'])
    assert run.error == '临时采集故障或请求超时' and run.execution_token is None
    assert len(await e.repo.history(e.db)) == 1


@pytest.mark.asyncio
async def test_inflight_request_renews_lease_before_saving(env, monkeypatch):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    calls = []
    original = e.repo.heartbeat

    async def tracked(*args, **kwargs):
        calls.append(1)
        return await original(*args, **kwargs)

    monkeypatch.setattr(e.repo, 'heartbeat', tracked)

    async def delayed():
        await asyncio.sleep(0.025)
        return e.batch([], {})

    e.state.batches = [delayed]
    result = await e.collection.PipelineCollectionService.execute(
        e.db, r['id'], registry=e.registry, clock=e.clock, pulse_seconds=0.005
    )
    assert result['status'] == 'success' and len(calls) >= 4


@pytest.mark.asyncio
async def test_disable_prevents_retry_and_stop_prevents_auto_retry(env):
    e = env
    s = await source(e, config={'retry': {'enabled': True, 'max_retries': 3}})
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=60)
    await e.repo.finish(e.db, r['id'], run.execution_token, now=NOW, error='临时采集故障或请求超时')
    await e.service.set_enabled(e.db, s['id'], False, registry=e.registry, clock=e.clock)
    assert (
        await e.service.retry_collection_run(e.db, r['id'], automatic=True, registry=e.registry, clock=e.clock) is None
    )
    await e.service.set_enabled(e.db, s['id'], True, registry=e.registry, clock=e.clock)
    second = await enqueue(e, s['id'], 'manual:second')
    run = await e.repo.claim(e.db, second['id'], now=NOW, lease_seconds=60)
    token = run.execution_token
    await e.service.stop_collection_run(e.db, second['id'], clock=e.clock)
    await e.repo.finish(e.db, second['id'], token, now=NOW, error='临时采集故障或请求超时')
    assert (
        await e.service.retry_collection_run(e.db, second['id'], automatic=True, registry=e.registry, clock=e.clock)
        is None
    )


@pytest.mark.asyncio
async def test_no_resume_adapter_discards_parent_checkpoint(env):
    e = env
    e.registry.adapters['fixed'] = e.collection.Adapter(
        e.registry.adapters['fixed'].factory, ('website',), ('example.test',), False
    )
    s = await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=60)
    token = run.execution_token
    run.checkpoint = {'page': 3}
    await e.db.commit()
    await e.repo.finish(e.db, r['id'], token, now=NOW, error='临时采集故障或请求超时')
    retry = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    assert retry['checkpoint'] == {}


@pytest.mark.parametrize(
    'values',
    [
        {'status': 'running'},
        {'status': 'stopping'},
        {'status': 'success', 'finished_at': NOW, 'failed_count': 1, 'fetched_count': 1},
        {'saved_count': 1, 'fetched_count': 0},
        {'status': 'failed', 'finished_at': NOW},
        {'trigger_type': 'retry', 'parent_id': None},
        {'started_at': NOW},
    ],
)
@pytest.mark.asyncio
async def test_row_checks_reject_invalid_states(env, values):
    e = env
    s = await source(e)
    attrs = dict(
        id=900003,
        source_id=int(s['id']),
        trigger_type='manual',
        request_id=900003,
        available_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    attrs.update(values)
    e.db.add(e.models.PipelineCrawlRun(**attrs))
    with pytest.raises(IntegrityError):
        await e.db.commit()
    await e.db.rollback()


def test_timezone_cron_and_dst_policy(env):
    next_time = env.sources.next_occurrence('0 8 * * *', 'Asia/Shanghai', NOW)
    assert next_time == NOW + timedelta(days=1)
    spring = datetime(2026, 3, 8, 6, tzinfo=timezone.utc)
    result = env.sources.next_occurrence('30 2 * * *', 'America/New_York', spring)
    assert result == datetime(2026, 3, 9, 6, 30, tzinfo=timezone.utc)


def test_dto_rejects_legacy_fields_and_coerced_enabled(env):
    from pydantic import ValidationError

    schema = importlib.import_module('app.intelligence.schemas.collection')
    with pytest.raises(ValidationError):
        schema.SourceSave(name='a', type='website', adapter='fixed', handoff_mode='external')
    with pytest.raises(ValidationError):
        schema.SourceEnabled(is_enabled='false')


@pytest.mark.asyncio
async def test_manual_idempotency_survives_source_config_change_and_disabling(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    await execute(e, r['id'])
    await e.service.set_enabled(e.db, s['id'], False, registry=e.registry, clock=e.clock)
    e.registry.adapters.clear()
    assert (await enqueue(e, s['id']))['id'] == r['id']


@pytest.mark.asyncio
async def test_admin_isolation_confirmation_is_explicit_and_terminal_safe(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=60)
    await e.service.stop_collection_run(e.db, r['id'], clock=e.clock)
    with pytest.raises(e.conflict):
        await e.service.confirm_isolated_stop(e.db, r['id'], worker_isolated=False, clock=e.clock)
    result = await e.service.confirm_isolated_stop(e.db, r['id'], worker_isolated=True, clock=e.clock)
    assert result['status'] == 'cancelled'
    other = await enqueue(e, s['id'], 'manual:other')
    await execute(e, other['id'])
    with pytest.raises(e.conflict):
        await e.service.confirm_isolated_stop(e.db, other['id'], worker_isolated=True, clock=e.clock)


@pytest.mark.asyncio
async def test_generic_scheduler_does_not_bootstrap_or_connect_database(env):
    scheduler_module = importlib.import_module('app.intelligence.tasks.collection_scheduler')

    class Scheduler:
        def __init__(self):
            self.jobs, self.removed = {}, []

        def get_jobs(self):
            return [SimpleNamespace(id='_pipesight_collection_old-source'), SimpleNamespace(id='unrelated')]

        def remove_job(self, job_id):
            self.removed.append(job_id)

        def add_job(self, function, trigger, **kwargs):
            assert trigger == 'interval'
            assert 'cron' not in kwargs
            self.jobs[kwargs['id']] = (function, kwargs)

    scheduler = Scheduler()
    jobs = await scheduler_module.register_real_collection_schedules(scheduler)
    assert len(jobs) == 3 and scheduler.removed == ['_pipesight_collection_old-source']
    assert all(job[1]['coalesce'] and job[1]['max_instances'] == 1 for job in scheduler.jobs.values())


@pytest.mark.asyncio
async def test_configuration_fault_never_auto_retries_and_masks_exception(env):
    e = env
    s = await source(e, config={'retry': {'enabled': True, 'max_retries': 3}})
    r = await enqueue(e, s['id'])
    e.state.batches = [e.collection.ConfigurationError('password=SECRET')]
    assert (await execute(e, r['id']))['status'] == 'failed'
    run = await e.repo.run(e.db, r['id'])
    assert 'SECRET' not in run.error
    assert len(await e.repo.history(e.db)) == 1
    with pytest.raises(e.conflict):
        await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)


@pytest.mark.asyncio
async def test_lease_expiring_during_batch_rolls_back_content_and_counts(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=60)
    with pytest.raises(e.lost):
        await e.persistence.CollectionPersistenceService.save_batch(
            e.db,
            r['id'],
            run.execution_token,
            [{'title': '耗时写入', 'url': 'https://example.test/expired'}],
            {'page': 1},
            now=NOW,
            clock=lambda: NOW + timedelta(seconds=61),
        )
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert (await e.repo.run(e.db, r['id'])).fetched_count == 0


def existing_samples():
    import json

    # Repository's already-curated metadata, not fresh HTTP captures. The tests
    # reconstruct the old collectors' HTML/JSON wire envelopes from these rows.
    path = ROOT.parents[1] / 'data' / 'curated' / 'homepage-real-content-20261014.json'
    return json.loads(path.read_text())['records']


def replay_transport(e, monkeypatch, handler):
    import httpx

    bridge = importlib.import_module('app.intelligence.integrations.public_source_bridge')
    clients, requests = [], []

    async def dispatch(request):
        requests.append(request)
        return await handler(request)

    def client(config):
        instance = httpx.AsyncClient(transport=httpx.MockTransport(dispatch), trust_env=False, follow_redirects=False)
        clients.append(instance)
        return instance

    monkeypatch.setattr(bridge, 'make_client', client)
    e.registry = e.collection.ADAPTERS
    return SimpleNamespace(bridge=bridge, clients=clients, requests=requests)


@pytest.mark.asyncio
async def test_real_pipechina_bridge_replays_existing_samples_as_batches(env, monkeypatch):
    import html

    import httpx

    e = env
    samples = [row for row in existing_samples() if row['kind'] == 'news']
    by_path = {httpx.URL(row['url']).path: row for row in samples}

    async def handler(request):
        if request.url.path == '/groupnews.html':
            body = ''.join(
                f'<div class="item"><a href="{path}">{html.escape(row["title"])}</a><span>{row["original_date"]}</span></div>'
                for path, row in by_path.items()
            )
        else:
            row = by_path[request.url.path]
            # A bounded fixture excerpt, not a claim that this is the full page.
            body = f'<div class="title">{html.escape(row["title"])}</div><span class="span3">{row["original_date"]}</span><div class="text content_class">{html.escape(row["summary"])}</div>'
        return httpx.Response(200, text=body)

    replay = replay_transport(e, monkeypatch, handler)
    s = await source(
        e, adapter='pipechina_group_news', url='https://www.pipechina.com.cn/groupnews.html', config={'limit': 3}
    )
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    run = await e.repo.run(e.db, r['id'])
    assert (run.fetched_count, run.saved_count, run.failed_count) == (3, 3, 0)
    articles = e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert {row.title for row in articles} == {row['title'] for row in samples}
    assert all(row.author is None and row.published_at is not None for row in articles)
    assert len(replay.requests) == 4 and all(client.is_closed for client in replay.clients)
    assert not e.state.category_requests  # Disabled-only category set needs no model.
    legacy = importlib.import_module('app.intelligence.integrations.public_sources')

    def cached_page(url, **kwargs):
        if url.endswith('/groupnews.html'):
            return ''.join(
                f'<div class="item"><a href="{path}">{html.escape(row["title"])}</a><span>{row["original_date"]}</span></div>'
                for path, row in by_path.items()
            )
        row = by_path[httpx.URL(url).path]
        return f'<div class="title">{html.escape(row["title"])}</div><span class="span3">{row["original_date"]}</span><div class="text content_class">{html.escape(row["summary"])}</div>'

    monkeypatch.setattr(legacy, '_fetch_text', cached_page)
    old_records = legacy.collect_pipechina_records(legacy.DEFAULT_PIPECHINA_ENDPOINT, {'limit': 3})
    assert {row.title: row.content for row in articles} == {row['title']: row['body'] for row in old_records}


@pytest.mark.asyncio
async def test_real_crossref_bridge_replays_existing_metadata_in_multiple_pages(env, monkeypatch):
    import json

    import httpx

    e = env
    samples = [row for row in existing_samples() if row['kind'] == 'paper']
    items = [
        {
            'title': [row['title']],
            'DOI': row['doi'],
            'URL': row['url'],
            'author': [{'family': author} for author in row['authors']],
            'container-title': [row['journal']],
            'abstract': row['summary'],
            'published': {'date-parts': [[int(value) for value in row['original_date'].split('-')]]},
        }
        for row in samples
    ]

    async def handler(request):
        assert request.url.host == 'api.crossref.org' and request.url.path == '/works'
        assert request.url.params['filter'] == 'from-pub-date:2022-01-01,type:journal-article'
        offset, count = int(request.url.params['offset']), int(request.url.params['rows'])
        return httpx.Response(200, json={'message': {'items': items[offset : offset + count]}})

    replay = replay_transport(e, monkeypatch, handler)
    s = await source(e, type='paper', adapter='crossref_works', url=None, config={'limit': 3, 'batch_size': 2})
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    papers = e.db.sync.scalars(select(e.content.PipelinePaper)).all()
    assert {row.published_date for row in papers} == {row['original_date'] for row in samples}
    assert len(papers) == 3 and all(not hasattr(row, 'content') for row in papers)
    assert [request.url.params['offset'] for request in replay.requests] == ['0', '2']
    assert all(client.is_closed for client in replay.clients)
    legacy = importlib.import_module('app.intelligence.integrations.public_sources')
    monkeypatch.setattr(legacy, '_fetch_text', lambda *args, **kwargs: json.dumps({'message': {'items': items}}))
    old_records = legacy.collect_crossref_records(legacy.DEFAULT_CROSSREF_ENDPOINT, {'limit': 3})
    assert {row.doi: (row.title, row.abstract, row.authors) for row in papers} == {
        row['doi']: (row['title'], row['abstract'], row['authors_text']) for row in old_records
    }


@pytest.mark.parametrize('adapter', ['pipechina_group_news', 'crossref_works'])
@pytest.mark.asyncio
async def test_real_bridge_stop_during_request_closes_stream_and_client(env, monkeypatch, adapter):
    import httpx

    e = env
    streams = []
    run_id = None

    class BlockingStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            async with AsyncMemorySession(e.engine) as other:
                stopped = await e.service.stop_collection_run(other, run_id, clock=e.clock)
                assert stopped['status'] == 'stopping' and stopped['finishedAt'] is None
            await asyncio.Event().wait()
            yield b'unreachable'

        async def aclose(self):
            self.closed = True

    async def handler(request):
        if request.url.path == '/groupnews.html':
            return httpx.Response(
                200, text='<div class="item"><a href="/front/news/3002671.html">Existing sample title</a></div>'
            )
        stream = BlockingStream()
        streams.append(stream)
        return httpx.Response(200, stream=stream)

    replay = replay_transport(e, monkeypatch, handler)
    s = await source(e, adapter=adapter, type='paper' if adapter == 'crossref_works' else 'website', url=None)
    r = await enqueue(e, s['id'])
    run_id = r['id']
    result = await e.collection.PipelineCollectionService.execute(
        e.db, run_id, registry=e.registry, clock=e.clock, pulse_seconds=0.005
    )
    assert result['status'] == 'cancelled'
    assert streams and all(stream.closed for stream in streams)
    assert all(client.is_closed for client in replay.clients)
    assert len(replay.requests) == (1 if adapter == 'crossref_works' else 2)
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert not e.db.sync.scalars(select(e.content.PipelinePaper)).all()


@pytest.mark.asyncio
async def test_real_bridge_generator_close_stops_further_pages(env, monkeypatch):
    import httpx

    e = env

    async def handler(request):
        return httpx.Response(
            200, json={'message': {'items': [{'title': ['Existing sample'], 'DOI': '10.1234/example'}]}}
        )

    replay = replay_transport(e, monkeypatch, handler)
    snapshot = {'adapter': 'crossref_works', 'type': 'paper', 'url': None, 'config': {'limit': 3, 'batch_size': 1}}
    iterator = e.registry.get('crossref_works').factory(snapshot, {})
    batch = await anext(iterator)
    assert len(batch.records) == 1
    await iterator.aclose()
    assert len(replay.requests) == 1 and replay.clients[0].is_closed


@pytest.mark.parametrize('status', [302, 403, 429, 503])
@pytest.mark.asyncio
async def test_real_bridge_http_failures_are_not_fake_success(env, monkeypatch, status):
    import httpx

    e = env

    async def handler(request):
        return httpx.Response(status, headers={'Location': 'http://127.0.0.1/secret'}, text='Cookie=SECRET')

    replay = replay_transport(e, monkeypatch, handler)
    s = await source(e, type='paper', adapter='crossref_works', url=None)
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'failed'
    run = await e.repo.run(e.db, r['id'])
    assert 'SECRET' not in run.error and run.fetched_count == 0
    assert len(replay.requests) == 1 and replay.clients[0].is_closed


@pytest.mark.asyncio
async def test_no_source_returns_explicit_message_and_formal_task_dtos(env):
    e = env
    assert '尚未配置采集来源' in (await e.service.list_sources(e.db))['message']
    assert '尚未配置采集来源' in (await e.service.list_collection_tasks(e.db))['message']
    s = await source(e)
    assert s['sourceId'] == s['id'] == s['source_code'] and s['isEnabled'] is True
    tasks = await e.service.list_collection_tasks(e.db)
    assert tasks['rows'][0]['latestRunId'] is None and tasks['rows'][0]['status'] == 'waiting'
    r = await enqueue(e, s['id'])
    tasks = await e.service.list_collection_tasks(e.db)
    assert tasks['rows'][0]['sourceId'] == s['id'] and tasks['rows'][0]['latestRunId'] == r['id']
    assert tasks['rows'][0]['isEnabled'] and tasks['rows'][0]['status'] == 'queued'
    detail = await e.service.get_collection_run_detail(e.db, r['id'])
    assert detail['runId'] == r['id'] and detail['sourceId'] == s['id']


async def configured_category(e, *, kind='all', enabled=True):
    e.db.add(
        e.ai_model(
            id=1,
            provider='offline-test',
            code='test',
            base_url='https://example.test/model',
            capabilities=['text_generate'],
            parameters={},
            is_enabled=True,
        )
    )
    e.db.add(
        e.content.PipelineCategory(
            id=900101,
            name='管理员类别',
            prompt='管理员实际分类提示词',
            model_id=1,
            applies_to=kind,
            is_enabled=enabled,
            sort_order=0,
        )
    )
    await e.db.commit()


@pytest.mark.parametrize('source_type', ['website', 'wechat'])
@pytest.mark.asyncio
async def test_real_category_service_called_outside_run_locks_and_saved(env, source_type):
    e = env
    await configured_category(e, kind='news')
    s = await source(e, type=source_type)
    r = await enqueue(e, s['id'])
    e.state.batches = [
        e.batch([{'title': '管网新闻', 'url': 'https://example.test/article', 'content': '真实采集正文输入'}], {})
    ]
    assert (await execute(e, r['id']))['status'] == 'success'
    article = e.db.sync.scalars(select(e.content.PipelineArticle)).one()
    assert article.category_id == 900101
    model, call = e.state.category_requests[0]
    assert model['id'] == 1 and '管理员实际分类提示词' in call['system_prompt']
    assert '真实采集正文输入' in call['prompt']


@pytest.mark.asyncio
async def test_paper_classification_never_receives_fulltext_and_failure_retries(env):
    e = env
    await configured_category(e, kind='paper')
    s = await source(e, type='paper')
    r = await enqueue(e, s['id'])
    e.state.batches = [
        e.batch(
            [{'title': '论文', 'doi': '10.1234/abstract', 'abstract': '实际摘要', 'content': 'SECRET_FULLTEXT'}], {}
        )
    ]
    e.state.category_reply = '{"match":[true,false]}'
    assert (await execute(e, r['id']))['status'] == 'failed'
    run = await e.repo.run(e.db, r['id'])
    assert (run.fetched_count, run.saved_count, run.failed_count) == (1, 0, 1)
    assert 'SECRET_FULLTEXT' not in e.state.category_requests[0][1]['prompt']
    retry = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    e.state.category_reply = '{"match":true}'
    e.clock = lambda: NOW + timedelta(seconds=30)
    assert (await execute(e, retry['id']))['status'] == 'success'
    assert e.db.sync.scalars(select(e.content.PipelinePaper)).one().category_id == 900101


@pytest.mark.asyncio
async def test_stop_while_classifying_cancels_model_task_without_writing(env):
    e = env
    await configured_category(e)
    s = await source(e)
    r = await enqueue(e, s['id'])
    cleaned = []

    async def waiting_model(classification_db):
        # This offline fake releases its read transaction before simulating an
        # in-flight model call. The real service is unchanged/main-owned.
        await classification_db.rollback()
        async with AsyncMemorySession(e.engine) as other:
            stopped = await e.service.stop_collection_run(other, r['id'], clock=e.clock)
            assert stopped['status'] == 'stopping'
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.append(True)

    e.state.category_reply = waiting_model
    e.state.batches = [e.batch([{'title': '待分类', 'url': 'https://example.test/classify'}], {})]
    result = await e.collection.PipelineCollectionService.execute(
        e.db, r['id'], registry=e.registry, clock=e.clock, pulse_seconds=0.005
    )
    assert result['status'] == 'cancelled' and cleaned
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()


@pytest.mark.asyncio
async def test_bad_success_response_is_failure_and_resources_close(env, monkeypatch):
    import httpx

    e = env

    async def handler(request):
        return httpx.Response(200, text='<html>Login required: no news markup</html>')

    replay = replay_transport(e, monkeypatch, handler)
    s = await source(e, adapter='pipechina_group_news', url=None)
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'failed'
    assert replay.clients[0].is_closed and not e.db.sync.scalars(select(e.content.PipelineArticle)).all()


def load_collection_router(e, monkeypatch):
    from fastapi import APIRouter, Depends, HTTPException, Request

    def module(name, **members):
        stub = ModuleType(name)
        stub.__dict__.update(members)
        monkeypatch.setitem(sys.modules, name, stub)

    def preauth():
        async def check():
            pass

        return Depends(check)

    def role(name):
        async def check(request: Request):
            if request.headers.get('x-role') != name:
                raise HTTPException(status_code=403)

        return Depends(check)

    def permission(name):
        async def check(request: Request):
            if name not in request.headers.get('x-permissions', '').split(','):
                raise HTTPException(status_code=403)

        return Depends(check)

    def database():
        async def dependency():
            return e.db

        return Depends(dependency)

    logged = []

    def log(**kwargs):
        logged.append(kwargs)
        return lambda function: function

    class Router(APIRouter):
        def __init__(self, *, auto_register, **kwargs):
            assert auto_register is False
            super().__init__(**kwargs)

    module('app.system.api.dependencies', PreAuthDependency=preauth)
    module('common.annotation.log_annotation', Log=log)
    module('common.aspect.db_seesion', DBSessionDependency=database)
    module('common.aspect.interface_auth', RoleInterfaceAuthDependency=role, UserInterfaceAuthDependency=permission)
    module('common.enums.audit', BusinessType=SimpleNamespace(INSERT='insert', UPDATE='update'))
    module('common.http.responses', ResponseUtil=SimpleNamespace(success=lambda **kwargs: {'code': 200, **kwargs}))
    module('common.http.routing', APIRouterPro=Router)
    router = importlib.import_module('app.intelligence.api.collection_controller').collection_controller
    return router, logged


@pytest.mark.asyncio
async def test_formal_frontend_routes_call_services_with_camelcase_and_optional_body(env, monkeypatch):
    import httpx
    from fastapi import FastAPI

    e = env
    router, logged = load_collection_router(e, monkeypatch)
    app = FastAPI()
    app.include_router(router)
    headers = {
        'x-role': 'admin',
        'x-permissions': 'pipeline:source:list,pipeline:source:save,pipeline:task:list,pipeline:task:run',
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='https://offline.test', headers=headers
    ) as client:
        created = await client.post(
            '/pipeline/sources',
            json={'name': '已有采集器', 'type': 'paper', 'adapter': 'crossref_works', 'isEnabled': True},
        )
        assert created.status_code == 200
        s = created.json()['data']
        assert s['sourceId'] == s['id'] == s['source_code'] and s['isEnabled']
        listing = await client.get('/pipeline/sources')
        assert listing.json()['data']['total'] == 1
        queued = await client.post(f'/pipeline/tasks/{s["id"]}/run')
        assert queued.status_code == 200
        run_id = queued.json()['data']['runId']
        task = (await client.get('/pipeline/tasks')).json()['data']['rows'][0]
        assert task['latestRunId'] == run_id and task['sourceId'] == s['id'] and task['isEnabled']
        detail = (await client.get(f'/pipeline/tasks/runs/{run_id}')).json()['data']
        assert detail['runId'] == run_id and detail['sourceId'] == s['id']
        stopped = await client.post(f'/pipeline/tasks/runs/{run_id}/stop')
        assert stopped.json()['data']['status'] == 'cancelled'
        assert (await client.post(f'/pipeline/tasks/runs/{run_id}/retry')).status_code == 409
        disabled = await client.delete(f'/pipeline/sources/{s["id"]}')
        assert disabled.json()['data']['isEnabled'] is False
        assert (await client.post(f'/pipeline/tasks/{s["id"]}/run')).status_code == 409
        updated = await client.put(
            f'/pipeline/sources/{s["id"]}',
            json={'name': '已更新', 'type': 'paper', 'adapter': 'crossref_works', 'isEnabled': True},
        )
        assert updated.json()['data']['name'] == '已更新'
        denied = await client.get('/pipeline/tasks', headers={'x-role': 'user'})
        assert denied.status_code == 403
    assert logged and all(row['request_log_mode'] == 'summary' for row in logged)


@pytest.mark.asyncio
async def test_disabled_category_without_model_does_not_block_normal_collection(env):
    e = env
    e.db.add(
        e.content.PipelineCategory(
            id=900102,
            name='未配置模型类别',
            prompt='管理员提示词',
            model_id=None,
            applies_to='all',
            is_enabled=False,
            sort_order=0,
        )
    )
    await e.db.commit()
    s = await source(e)
    r = await enqueue(e, s['id'])
    e.state.batches = [e.batch([{'title': '正常新闻', 'url': 'https://example.test/no-model', 'content': '正文'}], {})]
    assert (await execute(e, r['id']))['status'] == 'success'
    assert e.db.sync.scalars(select(e.content.PipelineArticle)).one().category_id is None
    assert not e.state.category_requests


@pytest.mark.asyncio
async def test_frontend_source_payload_allows_blank_query_and_thirty_total_papers(env):
    e = env
    schema = importlib.import_module('app.intelligence.schemas.collection')
    payload = schema.SourceSave.model_validate(
        {
            'name': '前端默认论文来源',
            'type': 'paper',
            'url': None,
            'adapter': 'crossref_works',
            'cron': None,
            'timezone': 'Asia/Shanghai',
            'modelId': None,
            'isEnabled': True,
            'config': {'limit': 30, 'query': ''},
        }
    )
    result = await e.service.save(e.db, **payload.model_dump(), registry=e.collection.ADAPTERS, clock=e.clock)
    assert result['isEnabled'] and result['config']['limit'] == 30 and result['config']['query'] == ''
