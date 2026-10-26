"""Opt-in original-dump -> real Alembic CLI/asyncpg -> committed compact schema.

Creates a uniquely named database on the labelled local rehearsal container.
Never resets the existing rehearsal, imports application environment settings in
this process, connects to production, or changes an allowlist. The explicit
revision switch is used only after the local endpoint and database are checked.
"""

# Exact schema counts and the isolated published port are intentional literals.
# ruff: noqa: PLR2004

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from app import schema_migration as migration
from app.ruoyi_table_names import RUOYI_TABLE_NAMES, inventory, row_fingerprints
from app.schema_comments_v2 import COLUMN_COMMENTS as V2_COLUMN_COMMENTS
from app.schema_comments_v2 import TABLE_COMMENTS as V2_TABLE_COMMENTS

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
RUNTIME = ROOT / '.runtime/schema-rollout-ythNjXpI'
CONTAINER = 'pipesight-schema-rehearsal-ythnjxpi'


def _docker(*arguments: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(['docker', *arguments], input=input_bytes, check=True,
                          capture_output=True, timeout=60)


def _local_connection() -> dict:
    connection = json.loads((RUNTIME / 'rehearsal-connection.json').read_bytes())
    assert connection['host'] == '127.0.0.1' and connection['port'] == 19432
    assert connection['dbname'] == 'pipesight_rehearsal'
    labels = json.loads(_docker('inspect', '--format', '{{json .Config.Labels}}', CONTAINER).stdout)
    ports = json.loads(_docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', CONTAINER).stdout)
    assert labels['pipesight.schema-rollout'] == 'ythNjXpI'
    assert {'HostIp': '127.0.0.1', 'HostPort': '19432'} in ports['5432/tcp']
    return connection


def _url(connection: dict, database: str) -> sa.URL:
    assert database.startswith('pipesight_asyncpg_') and database.isidentifier()
    return sa.URL.create('postgresql+asyncpg', host=connection['host'], port=connection['port'],
                         username=connection['user'], password=connection['password'], database=database)


async def _prepare(connection: dict, database: str, snapshot: dict, archive: Path) -> tuple:
    engine = create_async_engine(_url(connection, database), hide_parameters=True)
    try:
        async with engine.connect() as bind:
            def read_source(sync: sa.Connection) -> tuple:
                assert sync.dialect.driver == 'asyncpg'
                migration.verify_source_snapshot(sync, snapshot, allow_live=True)
                plan = migration.preflight(sync, historical_timezone='Asia/Shanghai', allow_live=True)
                assert plan.summary['contract'] == '20261025-compact-v1'
                assert len(plan.source) == 47 and plan.summary['physical_table_count'] == 29
                return plan, migration.archive_plan(plan, archive)
            return await bind.run_sync(read_source)
    finally:
        await engine.dispose()


async def _verify(connection: dict, database: str, plan: migration.MigrationPlan) -> dict:
    engine = create_async_engine(_url(connection, database), hide_parameters=True)
    try:
        async with engine.connect() as bind:
            await bind.execute(sa.text('SET TRANSACTION READ ONLY'))
            def read_target(sync: sa.Connection) -> dict:
                assert sync.dialect.driver == 'asyncpg'
                # Alembic's CLI must have committed the new revision itself.
                assert sync.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == '20261025_compact_schema'
                plan.target['alembic_version'] = [{'version_num': '20261025_compact_schema'}]
                report = migration.verify_target(sync, plan)
                assert (report['tables'], report['fields'], report['foreign_keys']) == (29, 340, 35)
                report['comments'] = migration.verify_schema_comments(sync)
                report['access'] = migration.verify_access_contract(sync, plan.access_contract, plan.optional_tables)
                counts = {name: sync.execute(sa.text('SELECT count(*) FROM public.' + name)).scalar_one()
                          for name in ('news_articles', 'papers', 'categories', 'templates', 'basket_items', 'users', 'menus')}
                assert counts == {'news_articles': 6, 'papers': 3, 'categories': 11, 'templates': 6,
                                  'basket_items': 1, 'users': 2, 'menus': 85}
                assert sync.execute(sa.text("SELECT count(*) FROM menus WHERE component IN ('ai/chat/index','pipeline/governance/index','pipeline/filter/index') OR permissions LIKE 'ai:chat:%'")).scalar_one() == 0
                assert sync.execute(sa.text('SELECT name FROM menus WHERE id=2009')).scalar_one() == '模型与类别提示词'
                assert {r[0] for r in sync.execute(sa.text('SELECT published_date FROM papers'))} == {'2024-03', '2020-11', '2024-03-18'}
                report['counts'] = counts
                return report
            return await bind.run_sync(read_target)
    finally:
        await engine.dispose()


async def _v2_manifest(connection: dict, database: str) -> dict:
    engine = create_async_engine(_url(connection, database), hide_parameters=True)
    try:
        async with engine.connect() as bind:
            await bind.execute(sa.text('SET TRANSACTION READ ONLY'))
            await bind.execute(sa.text("SET LOCAL TIME ZONE 'UTC'"))
            def read_source(sync: sa.Connection) -> dict:
                names = inventory(sync)
                return {'revision': sync.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one(),
                        'tables': sorted(names), 'fingerprints': row_fingerprints(sync, names)}
            return await bind.run_sync(read_source)
    finally:
        await engine.dispose()


async def _verify_v2(connection: dict, database: str, manifest: dict) -> dict:
    engine = create_async_engine(_url(connection, database), hide_parameters=True)
    try:
        async with engine.connect() as bind:
            await bind.execute(sa.text('SET TRANSACTION READ ONLY'))
            await bind.execute(sa.text("SET LOCAL TIME ZONE 'UTC'"))
            def read_target(sync: sa.Connection) -> dict:
                assert sync.dialect.driver == 'asyncpg'
                revision = '20261025_restore_ruoyi_names'
                assert sync.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == revision
                expected = {RUOYI_TABLE_NAMES.get(name, name): value
                            for name, value in manifest['fingerprints'].items()}
                expected['alembic_version'] = [1, sync.execute(sa.text(
                    "SELECT md5(md5(row_to_json(t)::text)) FROM public.alembic_version t"
                )).scalar_one()]
                names = inventory(sync)
                assert names == set(V2_TABLE_COMMENTS)
                assert row_fingerprints(sync, names) == expected
                inspector = sa.inspect(sync)
                field_count = fk_count = 0
                for name in sorted(names):
                    columns = inspector.get_columns(name, schema='public')
                    assert {column['name']: column['comment'] for column in columns} == V2_COLUMN_COMMENTS[name]
                    assert inspector.get_table_comment(name, schema='public')['text'] == V2_TABLE_COMMENTS[name]
                    field_count += len(columns)
                    fk_count += len(inspector.get_foreign_keys(name, schema='public'))
                assert (len(names), field_count, fk_count) == (29, 340, 35)
                assert isinstance(next(c['type'] for c in inspector.get_columns('reports') if c['name'] == 'id'), sa.VARCHAR)
                assert sync.execute(sa.text("SELECT to_regclass('public.business_id_seq')")).scalar_one() is None
                return {'revision': revision, 'tables': len(names), 'fields': field_count,
                        'foreign_keys': fk_count, 'all_rows_unchanged_except_revision': True,
                        'frozen_v2_comments_verified': True, 'business_pk_remains_varchar': True}
            return await bind.run_sync(read_target)
    finally:
        await engine.dispose()


@pytest.mark.skipif(os.environ.get('PIPESIGHT_ASYNCPG_ALEMBIC_REHEARSE') != '1',
                    reason='Explicit original-dump/local-container Alembic CLI rehearsal only')
def test_original_dump_migrates_through_real_alembic_asyncpg_cli() -> None:
    connection = _local_connection()
    dump = (RUNTIME / 'database-before.dump').read_bytes()
    snapshot = json.loads((RUNTIME / 'database-before.json').read_bytes())
    assert hashlib.sha256(dump).hexdigest() == snapshot['sha256']
    database = 'pipesight_asyncpg_' + uuid.uuid4().hex[:12]
    # Unique database, no DROP/clean/reset of any existing database.
    _docker('exec', CONTAINER, 'createdb', '-U', connection['user'], database)
    _docker('exec', '-i', CONTAINER, 'pg_restore', '-U', connection['user'], '-d', database,
            '--no-owner', '--no-privileges', '--exit-on-error', '--single-transaction', input_bytes=dump)
    archive = RUNTIME / (database + '-retirement.json')
    plan, digest = asyncio.run(_prepare(connection, database, snapshot, archive))
    environment = {
        **os.environ, 'DB_HOST': '127.0.0.1', 'DB_PORT': '19432', 'DB_DATABASE': database,
        'DB_USERNAME': connection['user'], 'DB_PASSWORD': connection['password'], 'DB_TYPE': 'postgresql',
        'DB_ECHO': 'false', 'PYTHONPATH': str(BACKEND / 'src'),
        'INSIGHTHUB_DB_HOST': '127.0.0.1', 'INSIGHTHUB_DB_PORT': '19432',
        'INSIGHTHUB_DB_DATABASE': database, 'INSIGHTHUB_DB_USERNAME': connection['user'],
        'INSIGHTHUB_DB_PASSWORD': connection['password'],
    }
    # Exercise exactly the production entry point: command.upgrade -> env.py ->
    # async_engine_from_config -> asyncpg -> run_sync(do_run_migrations).
    result = subprocess.run([
        sys.executable, '-m', 'alembic', '-c', 'alembic.ini',
        '-x', f'compact_archive={archive}', '-x', f'compact_archive_sha256={digest}',
        '-x', f'compact_source_snapshot={RUNTIME / "database-before.json"}',
        '-x', 'historical_timezone=Asia/Shanghai', '-x', 'compact_allow_live=true',
        'upgrade', '20261025_compact_schema',
    ], cwd=BACKEND, env=environment, capture_output=True, timeout=60, check=False)
    diagnostic = result.stderr.decode(errors='replace').replace(connection['password'], '[REDACTED]')
    assert result.returncode == 0, diagnostic[-9000:]
    report = asyncio.run(_verify(connection, database, plan))
    # Freeze a real intermediate v1 dump before invoking the historical v2
    # revision. Runtime v3 imports must not leak numeric IDs/comments backwards.
    backup = RUNTIME / (database + '-v2-backup')
    backup.mkdir(mode=0o700)
    intermediate_dump = _docker('exec', CONTAINER, 'pg_dump', '-U', connection['user'],
                                '-d', database, '-Fc').stdout
    manifest = asyncio.run(_v2_manifest(connection, database))
    manifest['sha256'] = hashlib.sha256(intermediate_dump).hexdigest()
    for filename, payload in [('database-before.dump', intermediate_dump),
                              ('database-before.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode())]:
        fd = os.open(backup / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
    v2_result = subprocess.run([
        sys.executable, '-m', 'alembic', '-c', 'alembic.ini',
        '-x', f'ruoyi_backup={backup}', 'upgrade', '20261025_restore_ruoyi_names',
    ], cwd=BACKEND, env=environment, capture_output=True, timeout=60, check=False)
    diagnostic = v2_result.stderr.decode(errors='replace').replace(connection['password'], '[REDACTED]')
    assert v2_result.returncode == 0, diagnostic[-9000:]
    report['historical_v2'] = asyncio.run(_verify_v2(connection, database, manifest))
    report['historical_v2']['backup_path'] = str(backup)
    report.update(database=database, driver='asyncpg', entrypoint='python -m alembic',
                  original_restored_tables=47, original_dump_sha256=snapshot['sha256'],
                  archive_path=str(archive), archive_sha256=digest, cli_returncode=result.returncode,
                  existing_rehearsal_reset=False, real_database_connected=False,
                  source_owner_acl_replayed=False)
    # Generated evidence is retained with the independent DB for inspection;
    # neither existing rehearsal nor source credentials are included.
    evidence = RUNTIME / (database + '-verification.json')
    fd = os.open(evidence, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'database': database, 'evidence': str(evidence), 'tables': 29,
                      'fields': 340, 'foreign_keys': 35, 'driver': 'asyncpg'}))
