"""Opt-in real PG18 verification; fixed localhost rehearsal only, all writes rollback.

PIPESIGHT_COLLECTION_PG18=1 python -m pytest tests/intelligence/test_collection_pg18.py
No migrations/DDL, production configuration, real crawls or real model calls.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT.parent
APP = ROOT / 'src' / 'app'
CONNECTION = PROJECT / '.runtime/schema-rollout-ythNjXpI/rehearsal-connection.json'
CONTAINER = 'pipesight-schema-rehearsal-ythnjxpi'
TABLES = ('data_sources', 'collection_runs', 'news_articles', 'papers', 'categories', 'ai_models')
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get('PIPESIGHT_COLLECTION_PG18') != '1',
        reason='Explicit localhost PG18 rehearsal opt-in only',
    ),
]


def rehearsal_connection() -> dict:
    info = json.loads(CONNECTION.read_text())
    if (info.get('host'), int(info.get('port', 0)), info.get('dbname')) != (
        '127.0.0.1',
        19432,
        'pipesight_rehearsal',
    ):
        raise AssertionError('Refusing any destination except the exact localhost rehearsal')
    labels = subprocess.run(
        ['docker', 'inspect', '--format', '{{json .Config.Labels}}', CONTAINER],
        check=True,
        capture_output=True,
        text=True,
    )
    ports = subprocess.run(
        ['docker', 'inspect', '--format', '{{json .NetworkSettings.Ports}}', CONTAINER],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(labels.stdout).get('pipesight.schema-rollout') == 'ythNjXpI'
    assert {'HostIp': '127.0.0.1', 'HostPort': '19432'} in json.loads(ports.stdout)['5432/tcp']
    return info


@pytest.fixture
def domain(monkeypatch):
    # Isolate production ORM classes without importing config.database's default
    # engine or retired model aggregations. This is NOT a mocked DB/model schema.
    for name in list(sys.modules):
        if name in {'app', 'app.business_ids'} or name.startswith('app.intelligence'):
            monkeypatch.delitem(sys.modules, name)
    for name, path in [('app', APP), ('app.intelligence', APP / 'intelligence')]:
        package = ModuleType(name)
        package.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, package)
    for leaf in ('models', 'repositories', 'services', 'integrations', 'schemas', 'api'):
        name = f'app.intelligence.{leaf}'
        package = ModuleType(name)
        package.__path__ = [str(APP / 'intelligence' / leaf)]
        monkeypatch.setitem(sys.modules, name, package)

    class Base(DeclarativeBase):
        pass

    config = ModuleType('config.database')
    config.Base = Base
    monkeypatch.setitem(sys.modules, 'config.database', config)
    model = importlib.import_module('app.intelligence.models.collection')
    importlib.import_module('app.intelligence.models.ai_models')
    content = importlib.import_module('app.intelligence.models.content')
    repository = importlib.import_module('app.intelligence.repositories.collection_repository')
    collection = importlib.import_module('app.intelligence.services.collection')
    sources = importlib.import_module('app.intelligence.services.sources')
    persistence = importlib.import_module('app.intelligence.services.collection_persistence')
    bridge = importlib.import_module('app.intelligence.integrations.public_source_bridge')
    state = SimpleNamespace(batches=[], cleaned=False, clients=[], requests=[])

    async def fixed(snapshot, checkpoint):
        try:
            for batch in state.batches:
                if isinstance(batch, Exception):
                    raise batch
                yield batch
        finally:
            state.cleaned = True

    registry = collection.AdapterRegistry()
    registry.register('fixed-pg18', collection.Adapter(fixed, ('website', 'paper'), ('example.test',)))
    gateway = ModuleType('app.research.services.model_generation')

    async def forbidden_model(*args, **kwargs):
        raise AssertionError('No model network call is authorized in this rehearsal')

    gateway.ModelGateway = SimpleNamespace(call=forbidden_model)
    monkeypatch.setitem(sys.modules, gateway.__name__, gateway)
    yield SimpleNamespace(
        model=model,
        content=content,
        repository=repository,
        repo=repository.CollectionRepository,
        service=sources.IntelligenceSourceService,
        collection=collection,
        persistence=persistence.CollectionPersistenceService,
        bridge=bridge,
        registry=registry,
        state=state,
    )
    for name in list(sys.modules):
        if name.startswith('app.intelligence.'):
            sys.modules.pop(name, None)


async def fingerprints(connection) -> dict:
    result = {}
    for table in TABLES:  # Fixed identifiers, never user-provided SQL names.
        result[table] = tuple(
            (
                await connection.execute(
                    text(
                        f"SELECT count(*), md5(coalesce(string_agg(md5(row_to_json(t)::text), '' ORDER BY id), '')) FROM public.{table} t",
                    )
                )
            ).one()
        )
    return result


@pytest_asyncio.fixture
async def pg(domain, monkeypatch):
    info = rehearsal_connection()  # Reject before creating an engine or socket.
    original_connect = socket.socket.connect

    def local_only(sock, address):
        if not isinstance(address, tuple) or address[:2] != ('127.0.0.1', 19432):
            raise AssertionError('Only localhost:19432 DB sockets are authorized')
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', local_only)
    url = URL.create(
        'postgresql+asyncpg',
        username=info['user'],
        password=info['password'],
        host=info['host'],
        port=info['port'],
        database=info['dbname'],
    )
    assert url.host == '127.0.0.1' and url.port == 19432 and url.database == 'pipesight_rehearsal'
    engine = create_async_engine(url, echo=False, hide_parameters=True, connect_args={'timeout': 5})
    try:
        async with engine.connect() as connection:
            identity = (
                await connection.execute(text("SELECT current_database(), current_setting('server_version_num')::int"))
            ).one()
            assert identity[0] == 'pipesight_rehearsal' and 180000 <= identity[1] < 190000
            for table, expected in [
                ('data_sources', domain.model.PipelineSource),
                ('collection_runs', domain.model.PipelineCrawlRun),
            ]:
                columns = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:table",
                            ),
                            {'table': table},
                        )
                    ).scalars()
                )
                assert columns == set(expected.__table__.columns.keys())
            baseline = await fingerprints(connection)
            await connection.rollback()
            outer = await connection.begin()
            sessions = async_sessionmaker(
                bind=connection, expire_on_commit=False, autoflush=False, join_transaction_mode='create_savepoint'
            )
            monkeypatch.setattr(domain.collection, 'classification_session_factory', lambda db: sessions)
            domain.engine, domain.connection, domain.sessions = engine, connection, sessions
            domain.now = datetime.now(timezone.utc)
            domain.clock = lambda: domain.now
            domain.prefix = f'collection-pg18-{uuid4().hex}'
            try:
                async with sessions() as db:
                    domain.db = db
                    yield domain
            finally:
                assert outer.is_active, 'Service escaped its savepoint and committed the outer transaction'
                await outer.rollback()
                assert await fingerprints(connection) == baseline, 'Rollback did not restore collection/content rows'
                await connection.rollback()
    finally:
        await engine.dispose()


async def new_source(e, *, kind='website', config=None, adapter='fixed-pg18'):
    return await e.service.save(
        e.db,
        name=f'{e.prefix}-{uuid4().hex[:8]}',
        type=kind,
        adapter=adapter,
        url=None if adapter != 'fixed-pg18' else 'https://example.test/feed',
        config=config or {},
        registry=e.registry,
        clock=e.clock,
    )


async def queue(e, source_id, suffix=None):
    return await e.service.queue_collection_run(
        e.db, source_id, request_id=f'{e.prefix}:{suffix or uuid4().hex}', registry=e.registry, clock=e.clock
    )


async def claim(e, run_id, seconds=60):
    run = await e.repo.claim(e.db, run_id, now=e.now, lease_seconds=seconds)
    return run.execution_token


async def test_pg_queued_stop_and_disabled_source_prevent_claim(pg):
    e = pg
    s = await new_source(e)
    r = await queue(e, s['id'])
    result = await e.service.stop_collection_run(e.db, r['id'], clock=e.clock)
    assert result['status'] == 'cancelled' and result['stopRequestedAt'] and result['finishedAt']
    assert result['startedAt'] is None
    assert await e.repo.claim(e.db, r['id'], now=e.now, lease_seconds=60) is None
    other = await queue(e, s['id'])
    disabled = await e.service.set_enabled(e.db, s['id'], False, registry=e.registry, clock=e.clock)
    assert disabled['isEnabled'] is False
    assert (await e.repo.run(e.db, other['id'])).status == 'cancelled'
    await e.service.set_enabled(e.db, s['id'], True, registry=e.registry, clock=e.clock)
    assert await e.repo.claim(e.db, other['id'], now=e.now, lease_seconds=60) is None


async def test_pg_running_stopping_fences_batches_until_executor_ack(pg):
    e = pg
    s = await new_source(e)
    r = await queue(e, s['id'])
    token = await claim(e, r['id'])
    result = await e.service.stop_collection_run(e.db, r['id'], clock=e.clock)
    assert result['status'] == 'stopping' and result['finishedAt'] is None
    assert (await queue(e, s['id']))['id'] == r['id']
    with pytest.raises(IntegrityError):
        async with e.db.begin_nested():
            e.db.add(
                e.model.PipelineCrawlRun(
                    source_id=int(s['id']),
                    trigger_type='manual',
                    request_id=f'{e.prefix}:duplicate-active',
                    available_at=e.now,
                    created_at=e.now,
                    updated_at=e.now,
                )
            )
            await e.db.flush()
    await e.db.commit()
    with pytest.raises(e.repository.LeaseLost):
        await e.persistence.save_batch(
            e.db,
            r['id'],
            token,
            [{'title': 'must not commit', 'url': f'https://example.test/{e.prefix}'}],
            {},
            now=e.now,
            clock=e.clock,
        )
    assert (await e.repo.finish(e.db, r['id'], token, now=e.now)).status == 'cancelled'
    assert (await e.service.stop_collection_run(e.db, r['id'], clock=e.clock))['status'] == 'cancelled'


async def test_pg_retry_child_snapshot_backoff_and_unique_parent(pg):
    e = pg
    s = await new_source(e, config={'retry': {'backoff_seconds': 10}})
    r = await queue(e, s['id'])
    token = await claim(e, r['id'])
    await e.repo.finish(e.db, r['id'], token, now=e.now, error='临时采集故障或请求超时')
    first = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    repeated = await e.service.retry_collection_run(
        e.db, r['id'], request_id=f'{e.prefix}:retry-again', registry=e.registry, clock=e.clock
    )
    assert first['id'] == repeated['id'] and first['parentId'] == r['id']
    assert first['availableAt'] == (e.now + timedelta(seconds=10)).isoformat()
    assert await e.repo.claim(e.db, first['id'], now=e.now, lease_seconds=60) is None
    parent = await e.repo.run(e.db, r['id'])
    child = await e.repo.run(e.db, first['id'])
    assert parent.status == 'failed' and parent.error and parent.finished_at
    assert child.config_snapshot == parent.config_snapshot and child.fetched_count == 0
    # Real PG partial index, not an application-layer mock.
    with pytest.raises(IntegrityError):
        async with e.db.begin_nested():
            e.db.add(
                e.model.PipelineCrawlRun(
                    source_id=int(s['id']),
                    parent_id=int(r['id']),
                    trigger_type='retry',
                    request_id=f'{e.prefix}:second-child',
                    status='cancelled',
                    stop_requested_at=e.now,
                    finished_at=e.now,
                    available_at=e.now,
                    created_at=e.now,
                    updated_at=e.now,
                )
            )
            await e.db.flush()
    await e.db.commit()


async def test_pg_composite_fk_refuses_cross_source_retry(pg):
    e = pg
    left, right = await new_source(e), await new_source(e)
    r = await queue(e, left['id'])
    token = await claim(e, r['id'])
    await e.repo.finish(e.db, r['id'], token, now=e.now, error='临时采集故障或请求超时')
    with pytest.raises(IntegrityError):
        async with e.db.begin_nested():
            e.db.add(
                e.model.PipelineCrawlRun(
                    source_id=int(right['id']),
                    parent_id=int(r['id']),
                    trigger_type='retry',
                    request_id=f'{e.prefix}:cross-source',
                    available_at=e.now,
                    created_at=e.now,
                    updated_at=e.now,
                )
            )
            await e.db.flush()
    await e.db.commit()


async def test_pg_lease_fencing_recovery_and_stopping_isolation(pg):
    e = pg
    s = await new_source(e)
    r = await queue(e, s['id'])
    token = await claim(e, r['id'], seconds=5)
    expired = e.now + timedelta(seconds=6)
    with pytest.raises(e.repository.LeaseLost):
        await e.persistence.save_batch(
            e.db,
            r['id'],
            token,
            [{'title': 'expired worker', 'url': f'https://example.test/{e.prefix}/expired'}],
            {},
            now=expired,
            clock=lambda: expired,
        )
    await e.repo.recover(e.db, r['id'], now=expired)
    with pytest.raises(e.repository.LeaseLost):
        await e.repo.finish(e.db, r['id'], token, now=expired)
    e.now = expired
    retry = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    e.now += timedelta(seconds=30)
    new_token = await claim(e, retry['id'], seconds=5)
    assert new_token != token
    with pytest.raises(e.repository.LeaseLost):
        await e.repo.heartbeat(e.db, retry['id'], token, now=e.now, lease_seconds=60)
    with pytest.raises(e.repository.LeaseLost):
        await e.persistence.save_batch(
            e.db,
            retry['id'],
            token,
            [{'title': 'old token', 'url': f'https://example.test/{e.prefix}/old-token'}],
            {},
            now=e.now,
            clock=e.clock,
        )
    await e.service.stop_collection_run(e.db, retry['id'], clock=e.clock)
    isolated = await e.repo.recover(e.db, retry['id'], now=e.now + timedelta(seconds=6))
    assert isolated.status == 'stopping' and isolated.execution_token is None and isolated.finished_at is None
    result = await e.service.confirm_isolated_stop(
        e.db, retry['id'], worker_isolated=True, clock=lambda: e.now + timedelta(seconds=7)
    )
    assert result['status'] == 'cancelled'


async def test_pg_real_two_connection_source_lock_serializes_operations(pg):
    e = pg
    # An existing source is visible to two uncommitted transactions. We do not
    # commit seed rows just to manufacture a concurrent test.
    source_id = (await e.connection.execute(select(e.model.PipelineSource.id).limit(1))).scalar_one()
    async with e.engine.connect() as left, e.engine.connect() as right:
        a, b = await left.begin(), await right.begin()
        try:
            stmt = select(e.model.PipelineSource.id).where(e.model.PipelineSource.id == source_id).with_for_update()
            await left.execute(stmt)
            await right.execute(text("SET LOCAL lock_timeout = '150ms'"))
            with pytest.raises(DBAPIError) as failure:
                await right.execute(stmt)
            assert getattr(failure.value.orig, 'sqlstate', None) == '55P03'
            await b.rollback()
            await a.rollback()
            assert (await right.execute(stmt)).scalar_one() == source_id
            await right.rollback()
        finally:
            if a.is_active:
                await a.rollback()
            if b.is_active:
                await b.rollback()


@pytest.mark.parametrize('adapter', ['pipechina_group_news', 'crossref_works'])
async def test_pg_real_adapter_offline_samples_work_with_production_content_models(pg, monkeypatch, adapter):
    import html

    e = pg
    samples = json.loads((ROOT / 'data/curated/homepage-real-content-20261014.json').read_text())['records']
    rows = [row for row in samples if row['kind'] == ('paper' if adapter == 'crossref_works' else 'news')]

    async def response(request):
        e.state.requests.append(str(request.url))
        if adapter == 'crossref_works':
            offset, count = int(request.url.params['offset']), int(request.url.params['rows'])
            items = [
                {
                    'title': [row['title']],
                    'DOI': row['doi'],
                    'URL': row['url'],
                    'abstract': row['summary'],
                    'author': [{'family': author} for author in row['authors']],
                    'container-title': [row['journal']],
                    'published': {'date-parts': [[int(part) for part in row['original_date'].split('-')]]},
                }
                for row in rows[offset : offset + count]
            ]
            return httpx.Response(200, json={'message': {'items': items}})
        if request.url.path == '/groupnews.html':
            return httpx.Response(
                200,
                text=''.join(
                    f'<div class="item"><a href="{httpx.URL(row["url"]).path}">{html.escape(row["title"])}</a></div>'
                    for row in rows
                ),
            )
        row = next(row for row in rows if httpx.URL(row['url']).path == request.url.path)
        return httpx.Response(
            200,
            text=f'<div class="title">{html.escape(row["title"])}</div><span class="span3">{row["original_date"]}</span><div class="text content_class">{html.escape(row["summary"])}</div>',
        )

    def client(config):
        value = httpx.AsyncClient(transport=httpx.MockTransport(response), trust_env=False)
        e.state.clients.append(value)
        return value

    monkeypatch.setattr(e.bridge, 'make_client', client)
    e.registry = e.collection.ADAPTERS
    kind = 'paper' if adapter == 'crossref_works' else 'website'
    config = {'limit': 3, **({'batch_size': 2, 'query': ''} if kind == 'paper' else {})}
    s = await new_source(e, adapter=adapter, kind=kind, config=config)
    r = await queue(e, s['id'])
    result = await e.collection.PipelineCollectionService.execute(e.db, r['id'], registry=e.registry, clock=e.clock)
    assert result['status'] == 'success'
    run = await e.repo.run(e.db, r['id'])
    assert run.fetched_count == 3 and run.failed_count == 0
    assert len(e.state.requests) == (2 if kind == 'paper' else 4)
    assert all(value.is_closed for value in e.state.clients)
    if kind == 'paper':
        found = (
            (
                await e.db.execute(
                    select(e.content.PipelinePaper).where(e.content.PipelinePaper.doi.in_([row['doi'] for row in rows]))
                )
            )
            .scalars()
            .all()
        )
        assert len(found) == 3 and all(not hasattr(row, 'content') for row in found)


async def test_pg_task_and_source_dtos_match_frontend_contract(pg):
    e = pg
    s = await new_source(e)
    r = await queue(e, s['id'])
    row = next(row for row in (await e.service.list_collection_tasks(e.db))['rows'] if row['id'] == s['id'])
    assert row['sourceId'] == s['id'] and row['latestRunId'] == r['id'] and row['isEnabled']
    assert row['status'] == 'queued'
    detail = await e.service.get_collection_run_detail(e.db, r['id'])
    assert detail['runId'] == r['id'] and detail['sourceId'] == s['id']
    assert 'executionToken' not in detail and 'execution_token' not in detail


@pytest.mark.parametrize('adapter', ['pipechina_group_news', 'crossref_works'])
async def test_pg_adapter_stop_in_request_confirms_exit_and_closes_resources(pg, monkeypatch, adapter):
    e = pg
    streams = []
    active_run = None

    class WaitingStream(httpx.AsyncByteStream):
        closed = False
        cancelled = False

        async def __aiter__(self):
            async with e.sessions() as control:
                result = await e.service.stop_collection_run(control, active_run, clock=e.clock)
                assert result['status'] == 'stopping' and result['finishedAt'] is None
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
            yield b'never received'

        async def aclose(self):
            self.closed = True

    async def response(request):
        e.state.requests.append(str(request.url))
        if request.url.path == '/groupnews.html':
            return httpx.Response(
                200, text='<div class="item"><a href="/front/news/3002671.html">Offline existing sample</a></div>'
            )
        stream = WaitingStream()
        streams.append(stream)
        return httpx.Response(200, stream=stream)

    def client(config):
        value = httpx.AsyncClient(transport=httpx.MockTransport(response), trust_env=False)
        e.state.clients.append(value)
        return value

    monkeypatch.setattr(e.bridge, 'make_client', client)
    e.registry = e.collection.ADAPTERS
    s = await new_source(e, kind='paper' if adapter == 'crossref_works' else 'website', adapter=adapter)
    r = await queue(e, s['id'])
    active_run = r['id']
    result = await e.collection.PipelineCollectionService.execute(
        e.db, r['id'], registry=e.registry, clock=e.clock, pulse_seconds=0.01
    )
    assert result['status'] == 'cancelled'
    assert streams and all(stream.closed for stream in streams)
    assert all(stream.cancelled for stream in streams)
    assert all(value.is_closed for value in e.state.clients)
    run = await e.repo.run(e.db, r['id'])
    assert run.finished_at and run.execution_token is None and run.lease_expires_at is None
    assert run.fetched_count == run.saved_count == run.failed_count == 0
