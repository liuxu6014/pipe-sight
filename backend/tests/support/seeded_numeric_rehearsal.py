"""Explicit local-only nonempty numeric-ID rehearsal. Never reads live .env.

Creates a NEW database; retains it and private evidence. Does not drop/reset any
database or start/stop containers. Uses only the already labelled loopback PG18.
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import sqlalchemy as sa
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'backend'
CONTAINER = 'pipesight-schema-rehearsal-ythnjxpi'
BUSINESS = (
    'categories',
    'collection_runs',
    'data_sources',
    'digest_schedules',
    'generation_tasks',
    'knowledge_files',
    'model_calls',
    'news_articles',
    'papers',
    'report_assets',
    'reports',
    'templates',
)
NOW = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
SLOT = NOW.isoformat()
TEXT = '正文 opaque seed_shared seed_source seed_template，不能全局替换'


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, capture_output=True, timeout=60, **kwargs)


def private_json(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def validated_connection():
    manifest = json.loads(Path(os.environ['PIPESIGHT_PG_REHEARSAL_MANIFEST']).read_text())
    info = manifest['connection']
    assert (info['host'], info['port'], info['dbname']) == ('127.0.0.1', 19432, 'pipesight_rehearsal')
    labels = json.loads(docker('inspect', '--format', '{{json .Config.Labels}}', CONTAINER).stdout)
    ports = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', CONTAINER).stdout)
    assert labels['pipesight.schema-rollout'] == 'ythNjXpI'
    assert {'HostIp': '127.0.0.1', 'HostPort': '19432'} in ports['5432/tcp']
    return info


def insert(cursor, table, **values):
    # Reflect the restored OLD schema, not the concurrently edited ORM.
    cursor.execute(
        'SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s', ('public', table)
    )
    columns = {row[0] for row in cursor.fetchall()}
    for key in ('created_at', 'updated_at'):
        if key in columns:
            values.setdefault(key, NOW)
    assert set(values) <= columns, (table, set(values) - columns)
    query = sql.SQL('INSERT INTO public.{} ({}) VALUES ({}) RETURNING id').format(
        sql.Identifier(table),
        sql.SQL(',').join(map(sql.Identifier, values)),
        sql.SQL(',').join(sql.Placeholder() for _ in values),
    )
    cursor.execute(query, [Json(value) if isinstance(value, (dict, list)) else value for value in values.values()])
    return cursor.fetchone()[0]


def seed(info):
    with psycopg2.connect(**info) as db, db.cursor() as cur:
        cur.execute('SELECT id FROM sys_user WHERE id=1')
        if not cur.fetchone():
            insert(cur, 'sys_user', id=1, username='seeded_local', nickname='seeded local')
        # A disabled synthetic model is metadata only: no provider/network calls.
        model = insert(
            cur,
            'ai_models',
            name='seeded disabled',
            provider='local',
            code='seeded',
            base_url='http://127.0.0.1:1/never-call',
            credential_ref='env:SEEDED_NEVER_CALL',
            capabilities=['text_generate', 'image_generate'],
            parameters={},
            is_enabled=False,
        )
        category = insert(
            cur,
            'categories',
            id='seed_category',
            name='seeded numeric category',
            prompt=TEXT,
            model_id=model,
            is_enabled=False,
        )
        opaque = {
            'source_id': 'seed_source',
            'templateId': 'seed_template',
            'external': {'id': 'seed_shared', 'source_id': 'external-only'},
        }
        source = insert(
            cur,
            'data_sources',
            id='seed_source',
            name='seeded local source',
            type='website',
            adapter='manual',
            config=opaque,
            model_id=model,
            is_enabled=False,
        )
        article = insert(
            cur,
            'news_articles',
            id='seed_shared',
            source_id=source,
            category_id=category,
            title=TEXT,
            url='https://example.invalid/seeded-numeric',
            content=TEXT,
        )
        paper = insert(
            cur,
            'papers',
            id='seed_shared',
            source_id=source,
            category_id=category,
            title=TEXT,
            doi='10.9999/seeded-numeric',
            abstract=TEXT,
        )
        file = insert(
            cur,
            'knowledge_files',
            id='seed_shared',
            user_id=1,
            name=TEXT,
            filename='seed_shared.txt',
            storage_key='seed_source/seed_shared.txt',
            mime_type='text/plain',
            size=42,
            hash='a' * 64,
            extracted_text=TEXT,
            edited_text=TEXT,
            status='ready',
        )
        sections = [{'id': 'seed_template', 'title': TEXT, 'content': TEXT, 'citationIds': [1, 2, 3]}]
        template = insert(
            cur,
            'templates',
            id='seed_template',
            name='seeded template',
            purpose='research',
            prompt=TEXT,
            model_id=model,
            image_model_id=model,
            sections=sections,
            image_config={'prompt': TEXT, 'count': 1},
            is_enabled=False,
        )
        report = insert(
            cur, 'reports', id='seed_report', user_id=1, title=TEXT, type='research', template_id=template, content=TEXT
        )
        selected = [
            {'type': kind, 'id': value} for kind, value in [('article', article), ('paper', paper), ('file', file)]
        ]
        schedule = insert(
            cur,
            'digest_schedules',
            id='seed_schedule',
            user_id=1,
            name='seeded schedule',
            template_id=template,
            frequency='daily',
            run_time='08:00:00',
            timezone='Asia/Shanghai',
            selection_config={'source_ids': [source], 'category_ids': [category]},
            generation_config={'template_id': template, 'materials': selected, 'requirements': TEXT},
            is_enabled=False,
        )
        request = {
            'template_id': template,
            'report_id': report,
            'selected_item_ids': selected,
            'title': TEXT,
            'report_type': 'research',
        }
        snapshot = {
            'request': request,
            'request_fingerprint': hashlib.sha256(
                json.dumps(request, sort_keys=True, ensure_ascii=False, default=str).encode()
            ).hexdigest(),
            'template': {'id': template, 'sections': sections},
            'model': {'id': model, 'parameters': opaque},
            'image_model': {'id': model},
        }
        materials = [{**item, 'title': TEXT, 'content': TEXT, 'source': {'source_id': source}} for item in selected]
        task = insert(
            cur,
            'generation_tasks',
            id='seed_task',
            report_id=report,
            schedule_id=schedule,
            request_id=f'schedule:{schedule}:{SLOT}',
            config_snapshot=snapshot,
            materials=materials,
            result_content=TEXT,
        )
        insert(
            cur,
            'generation_tasks',
            id='seed_task_manual',
            report_id=report,
            request_id='manual:seed_schedule',
            status='failed',
            error='synthetic only',
            execution_token='seed_source',
            config_snapshot={'request': {'title': TEXT}, 'request_fingerprint': 'opaque-not-real-hash'},
            materials=[],
        )
        insert(
            cur,
            'report_assets',
            id='seed_asset',
            report_id=report,
            task_id=task,
            type='image',
            mime_type='image/png',
            prompt=TEXT,
            model_id=model,
            status='completed',
            storage_key='seed_source/seed_asset.png',
            config_snapshot={'template': {'id': template}, 'prompt': TEXT},
        )
        insert(
            cur,
            'model_calls',
            id='seed_call',
            task_id=task,
            model_id=model,
            capability='text_generate',
            status='failed',
            duration_ms=0,
            error='synthetic audit, no provider call',
        )
        citations = [
            {'id': index, 'type': item['type'], 'sourceId': item['id'], 'title': TEXT}
            for index, item in enumerate(selected, 1)
        ]
        version = insert(
            cur,
            'report_versions',
            report_id=report,
            version=1,
            title=TEXT,
            content=TEXT,
            sections=sections,
            citations=citations,
            quality_issues=[],
            model_snapshot=snapshot,
            source='manual',
            operator_id=1,
            operator_name='seeded',
        )
        run_snapshot = {
            'source_id': source,
            'source': {'id': source},
            'config': opaque,
            'checkpoint': {'source_id': source, 'cursor': 'seed_shared'},
        }
        parent = insert(
            cur,
            'collection_runs',
            id='seed_run_parent',
            source_id=source,
            trigger_type='schedule',
            request_id=f'schedule:{source}:{SLOT}',
            status='failed',
            error='synthetic failure',
            available_at=NOW,
            finished_at=NOW,
            config_snapshot=run_snapshot,
            checkpoint=opaque,
        )
        insert(
            cur,
            'collection_runs',
            id='seed_run_retry',
            source_id=source,
            parent_id=parent,
            trigger_type='retry',
            request_id=f'retry:{parent}',
            available_at=NOW,
            config_snapshot=run_snapshot,
            checkpoint=opaque,
        )
        baskets = [
            insert(cur, 'basket_items', user_id=1, action='basket', **{column: value})
            for column, value in [
                ('article_id', article),
                ('paper_id', paper),
                ('file_id', file),
                ('report_id', report),
            ]
        ]
        return {'model': model, 'version': version, 'baskets': baskets, 'opaque': opaque, 'sections': sections}


def backup(info, root):
    with psycopg2.connect(**info) as db:
        db.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with db.cursor() as cur:
            cur.execute("SET LOCAL TIME ZONE 'UTC'")
            cur.execute('SELECT pg_export_snapshot()')
            snapshot = cur.fetchone()[0]
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
            tables = [r[0] for r in cur.fetchall()]
            assert len(tables) == 29
            cur.execute('SELECT version_num FROM alembic_version')
            assert cur.fetchone()[0] == '20261025_restore_ruoyi_names'
            cur.execute(
                "SELECT table_name,data_type,column_default FROM information_schema.columns WHERE table_schema='public' AND column_name='id'"
            )
            columns = {r[0]: r[1:] for r in cur.fetchall()}
            assert all(columns[t][0] == 'character varying' and columns[t][1] is None for t in BUSINESS)
            fingerprints = {}
            for table in tables:
                cur.execute(
                    sql.SQL(
                        "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
                        '(SELECT md5(row_to_json(t)::text) h FROM public.{} t)s'
                    ).format(sql.Identifier(table))
                )
                fingerprints[table] = list(cur.fetchone())
            data = docker(
                'exec', CONTAINER, 'pg_dump', '-U', info['user'], '-d', info['dbname'], '-Fc', '--snapshot', snapshot
            ).stdout
            fd = os.open(root / 'database-before.dump', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            manifest = {
                'revision': '20261025_restore_ruoyi_names',
                'tables': tables,
                'fingerprints': fingerprints,
                'sha256': hashlib.sha256(data).hexdigest(),
                'fingerprint_timezone': 'UTC',
            }
            private_json(root / 'database-before.json', manifest)
            return manifest


async def actual_rollback(info, root, manifest, corrupt):
    from app import numeric_id_migration as migration

    url = sa.URL.create(
        'postgresql+asyncpg',
        username=info['user'],
        password=info['password'],
        host='127.0.0.1',
        port=19432,
        database=info['dbname'],
    )
    engine = create_async_engine(url, hide_parameters=True)
    archive = root / ('rollback-failure' if corrupt else 'rollback-success')
    archive.mkdir(mode=0o700)
    shutil.copy2(root / 'database-before.dump', archive / 'database-before.dump')
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()

            def exercise(bind):
                tables = set(manifest['tables'])
                original = migration._rows
                before = original(bind, tables)

                def rows(bind, tables, *, phase='source'):
                    result = original(bind, tables, phase=phase)
                    if corrupt and phase == 'target':
                        result['categories'][0]['name'] = 'injected projection mismatch'
                    return result

                migration._rows = rows
                try:
                    if corrupt:
                        try:
                            migration.migrate_numeric_ids(bind, manifest=manifest, backup_dir=archive)
                        except RuntimeError as error:
                            assert 'Target rows differ' in str(error)
                        else:
                            raise AssertionError('Injected failure was not rejected')
                        # Schema is string again after rollback: use old descriptor.
                        assert original(bind, tables, phase='source') == before
                        assert bind.scalar(sa.text("SELECT to_regclass('public.business_id_seq')")) is None
                    else:
                        migration.migrate_numeric_ids(bind, manifest=manifest, backup_dir=archive)
                finally:
                    migration._rows = original
                return before

            before = await connection.run_sync(exercise)
            await transaction.rollback()

            def verify(bind):
                assert migration._rows(bind, set(manifest['tables']), phase='source') == before
                assert bind.scalar(sa.text("SELECT to_regclass('public.business_id_seq')")) is None

            await connection.run_sync(verify)
    finally:
        await engine.dispose()


async def actual_queue_replay(info, root):
    """Real ORM/DAO existing path; no template/body/model loads, no writes."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    from sqlalchemy.ext.asyncio import AsyncSession

    from app import numeric_id_migration as migration
    from app.research.models.research_models import PipelineResearchJob
    from app.research.services.evidence import ResearchEvidenceService
    from app.research.services.jobs import ResearchJobService
    from exceptions.exception import ServiceException

    mapping = json.loads((root / 'numeric-id-mapping.json').read_text())['mappings']
    url = sa.URL.create(
        'postgresql+asyncpg',
        username=info['user'],
        password=info['password'],
        host='127.0.0.1',
        port=19432,
        database=info['dbname'],
    )
    engine = create_async_engine(url, hide_parameters=True)
    forbidden = AsyncMock(side_effect=AssertionError('Existing replay must not load templates, bodies or models'))
    templates = SimpleNamespace(get_published=forbidden, validate_models=forbidden)
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', record)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await session.begin()
            # Extra safety: this proof must be SELECT-only even if queue regresses.
            await session.execute(sa.text('SET TRANSACTION READ ONLY'))
            bind = await session.connection()
            before = await bind.run_sync(lambda sync: migration._rows(sync, set(migration.TABLE_COMMENTS)))
            task = await session.scalar(
                sa.select(PipelineResearchJob).where(PipelineResearchJob.id == mapping['generation_tasks']['seed_task'])
            )
            report = await session.execute(sa.text('SELECT user_id FROM reports WHERE id=:id'), {'id': task.report_id})
            owner = report.scalar_one()
            payload = deepcopy(task.config_snapshot['request'])
            payload['selected_item_ids'] = [str(item['id']) for item in task.materials]
            assert all(isinstance(item, str) and item.isdecimal() for item in payload['selected_item_ids'])
            payload['request_id'] = task.request_id

            def serializer(job, *, report):
                return {'id': str(job.id), 'report_id': str(report.id)}

            async def replay(data):
                return await ResearchJobService.queue(
                    session,
                    user_id=owner,
                    owner_name='seeded local',
                    payload=data,
                    stage_labels=[],
                    job_serializer=serializer,
                    template_service=templates,
                    schedule_id=task.schedule_id,
                    commit=False,
                )

            with patch.object(ResearchEvidenceService, 'resolve', forbidden):
                result = await replay(payload)
                assert result == {'id': str(task.id), 'report_id': str(task.report_id), 'reused': True}
                for change in ('type', 'selection'):
                    changed = deepcopy(payload)
                    if change == 'type':
                        changed['selected_item_ids'] = deepcopy(task.config_snapshot['request']['selected_item_ids'])
                        changed['selected_item_ids'][0]['type'] = 'paper'
                    else:
                        changed['selected_item_ids'] = changed['selected_item_ids'][:-1]
                    try:
                        await replay(changed)
                    except ServiceException as error:
                        assert error.message == '幂等键已被其他请求使用'
                    else:
                        raise AssertionError('Changed ' + change + ' unexpectedly reused the task')
            forbidden.assert_not_called()
            after = await bind.run_sync(lambda sync: migration._rows(sync, set(migration.TABLE_COMMENTS)))
            assert before == after, 'Existing replay modified database rows'
            assert not session.new and not session.dirty and not session.deleted
            assert all(statement.lstrip().upper().startswith(('SELECT', 'SET ')) for statement in statements)
            await session.rollback()
        # Verify after transaction rollback through a fresh connection as well.
        async with engine.connect() as bind:
            after_rollback = await bind.run_sync(lambda sync: migration._rows(sync, set(migration.TABLE_COMMENTS)))
            assert before == after_rollback
    finally:
        await engine.dispose()
    return {
        'actual_queue_existing_scalar_string_replay': 'passed',
        'actual_queue_changed_type_rejected': 'passed',
        'actual_queue_changed_selection_rejected': 'passed',
        'actual_queue_template_and_evidence_sentinel': 'passed',
        'actual_queue_readonly_rollback': 'passed',
    }


def verify(info, root, fixture):
    from app.business_ids import generation_request_fingerprint

    mapping = json.loads((root / 'numeric-id-mapping.json').read_text())['mappings']
    assert all(mapping[table] for table in BUSINESS), 'Nonempty paths must cover all 12 business tables'

    def mapped(table, old):
        return mapping[table][old]

    with psycopg2.connect(**info) as db, db.cursor(cursor_factory=RealDictCursor) as cur:

        def row(table, value):
            cur.execute(sql.SQL('SELECT * FROM public.{} WHERE id=%s').format(sql.Identifier(table)), (value,))
            return cur.fetchone()

        task = row('generation_tasks', mapped('generation_tasks', 'seed_task'))
        assert task['request_id'] == f'schedule:{mapped("digest_schedules", "seed_schedule")}:{SLOT}'
        assert task['report_id'] == mapped('reports', 'seed_report')
        assert task['result_content'] == TEXT
        for material, table in zip(task['materials'], ('news_articles', 'papers', 'knowledge_files'), strict=True):
            assert material['id'] == str(mapped(table, 'seed_shared')) and material['content'] == TEXT
            assert material['source']['source_id'] == str(mapped('data_sources', 'seed_source'))
        snap = task['config_snapshot']
        assert snap['template']['id'] == str(mapped('templates', 'seed_template'))
        assert snap['request']['report_id'] == str(mapped('reports', 'seed_report'))
        assert snap['request']['template_id'] == str(mapped('templates', 'seed_template'))
        assert [item['id'] for item in snap['request']['selected_item_ids']] == [
            str(mapped(table, 'seed_shared')) for table in ('news_articles', 'papers', 'knowledge_files')
        ]
        assert snap['model']['id'] == fixture['model'] and snap['model']['parameters'] == fixture['opaque']
        assert snap['request_fingerprint'] == generation_request_fingerprint(snap['request'], task['materials'])
        # Queue replay starts with raw numeric scalar IDs, not stored typed refs.
        # Frozen materials resolve each type without querying/decrypting sources.
        for field in ('materials', 'selected_item_ids'):
            replay = deepcopy(snap['request'])
            replay.pop('selected_item_ids')
            replay[field] = [int(material['id']) for material in task['materials']]
            replay['template_id'] = int(replay['template_id'])
            replay['report_id'] = int(replay['report_id'])
            replay['request_id'] = task['request_id']
            assert generation_request_fingerprint(replay, task['materials']) == snap['request_fingerprint']
        changed = deepcopy(snap['request'])
        changed['selected_item_ids'][0]['type'] = 'paper'
        assert generation_request_fingerprint(changed, task['materials']) != snap['request_fingerprint']
        manual = row('generation_tasks', mapped('generation_tasks', 'seed_task_manual'))
        assert (manual['request_id'], manual['execution_token']) == ('manual:seed_schedule', 'seed_source')
        parent = row('collection_runs', mapped('collection_runs', 'seed_run_parent'))
        child = row('collection_runs', mapped('collection_runs', 'seed_run_retry'))
        assert parent['request_id'] == f'schedule:{mapped("data_sources", "seed_source")}:{SLOT}'
        assert child['parent_id'] == parent['id'] and child['request_id'] == f'retry:{parent["id"]}'
        assert child['config_snapshot']['source']['id'] == str(parent['source_id'])
        assert child['config_snapshot']['config'] == child['checkpoint'] == fixture['opaque']
        assert row('data_sources', parent['source_id'])['config'] == fixture['opaque']
        assert child['config_snapshot']['source_id'] == str(parent['source_id'])
        schedule = row('digest_schedules', mapped('digest_schedules', 'seed_schedule'))
        assert schedule['selection_config']['source_ids'] == [str(parent['source_id'])]
        assert schedule['selection_config']['category_ids'] == [str(mapped('categories', 'seed_category'))]
        assert schedule['generation_config']['template_id'] == str(mapped('templates', 'seed_template'))
        assert schedule['generation_config']['requirements'] == TEXT
        asset = row('report_assets', mapped('report_assets', 'seed_asset'))
        assert (asset['task_id'], asset['report_id'], asset['model_id']) == (
            task['id'],
            task['report_id'],
            fixture['model'],
        )
        assert asset['config_snapshot']['template']['id'] == str(mapped('templates', 'seed_template'))
        assert asset['prompt'] == TEXT and asset['storage_key'] == 'seed_source/seed_asset.png'
        call = row('model_calls', mapped('model_calls', 'seed_call'))
        assert (call['task_id'], call['model_id']) == (task['id'], fixture['model'])
        version = row('report_versions', fixture['version'])
        assert version['sections'] == fixture['sections'] and version['content'] == TEXT
        assert version['model_snapshot']['template']['id'] == str(mapped('templates', 'seed_template'))
        assert row('templates', mapped('templates', 'seed_template'))['sections'] == fixture['sections']
        assert row('reports', task['report_id'])['content'] == TEXT
        assert row('knowledge_files', mapped('knowledge_files', 'seed_shared'))['extracted_text'] == TEXT
        for citation, table in zip(version['citations'], ('news_articles', 'papers', 'knowledge_files'), strict=True):
            assert citation['sourceId'] == str(mapped(table, 'seed_shared'))
        for basket, column, table, old in zip(
            fixture['baskets'],
            ('article_id', 'paper_id', 'file_id', 'report_id'),
            ('news_articles', 'papers', 'knowledge_files', 'reports'),
            ('seed_shared', 'seed_shared', 'seed_shared', 'seed_report'),
            strict=True,
        ):
            assert row('basket_items', basket)[column] == mapped(table, old)
        cur.execute('SELECT version_num FROM alembic_version')
        assert cur.fetchone()['version_num'] == '20261025_numeric_business_ids'
        cur.execute("SELECT count(*) n FROM pg_tables WHERE schemaname='public'")
        assert cur.fetchone()['n'] == 29
        cur.execute("SELECT count(*) n FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace")
        assert cur.fetchone()['n'] == 35
        cur.execute(
            "SELECT table_name,data_type,column_default FROM information_schema.columns WHERE table_schema='public' AND column_name='id'"
        )
        columns = {r['table_name']: r for r in cur.fetchall()}
        assert all(
            columns[t]['data_type'] == 'bigint' and 'business_id_seq' in columns[t]['column_default'] for t in BUSINESS
        )
        maximum = max(new for values in mapping.values() for new in values.values())
        cur.execute(
            "INSERT INTO categories(name,prompt,is_enabled) VALUES('seeded sequence rollback','x',false) RETURNING id"
        )
        first = cur.fetchone()['id']
        cur.execute(
            "INSERT INTO data_sources(name,type,adapter,is_enabled) VALUES('seeded sequence rollback','website','manual',false) RETURNING id"
        )
        second = cur.fetchone()['id']
        assert maximum < first < second
        db.rollback()
        return {
            'mapped_records': maximum,
            'seeded_tables': list(BUSINESS),
            'foreign_keys': 35,
            'numeric_primary_keys': 12,
            'json_and_system_keys': 'passed',
            'global_sequence_rollback': 'passed',
            'scalar_numeric_request_replay_fingerprint': 'passed',
            'explicit_type_change_conflicts': 'passed',
        }


def main():
    started_at = datetime.now(timezone.utc).isoformat()
    production_paths = [
        BACKEND / 'src/app/numeric_id_migration.py',
        BACKEND / 'src/app/business_ids.py',
        BACKEND / 'src/app/research/services/jobs.py',
        BACKEND / 'src/app/research/repositories/research_repository.py',
        BACKEND / 'alembic/versions/20261025_numeric_business_ids.py',
    ]
    production_hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in production_paths
    }

    def verify_code_unchanged():
        assert production_hashes == {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in production_paths
        }, 'Production migration code changed during rehearsal; rerun on a stable version'

    info = validated_connection()
    source_root = Path(os.environ['PIPESIGHT_NUMERIC_SEED_BACKUP'])
    dump = source_root / 'database-before.dump'
    source_manifest = json.loads((source_root / 'database-before.json').read_text())
    assert hashlib.sha256(dump.read_bytes()).hexdigest() == source_manifest['sha256']
    assert source_manifest['revision'] == '20261025_restore_ruoyi_names'
    database = 'pipesight_seeded_numeric_' + uuid.uuid4().hex[:12]
    assert database.isidentifier() and database.startswith('pipesight_seeded_numeric_')
    info['dbname'] = database
    root = Path(os.environ['PIPESIGHT_PG_EVIDENCE']) / database
    root.mkdir(mode=0o700)
    docker('exec', CONTAINER, 'createdb', '-U', info['user'], database)
    docker(
        'exec',
        '-i',
        CONTAINER,
        'pg_restore',
        '-U',
        info['user'],
        '-d',
        database,
        '--no-owner',
        '--no-privileges',
        '--exit-on-error',
        '--single-transaction',
        input=dump.read_bytes(),
    )
    fixture = seed(info)
    manifest = backup(info, root)
    env = {
        **os.environ,
        'DB_HOST': '127.0.0.1',
        'DB_PORT': '19432',
        'DB_DATABASE': database,
        'DB_USERNAME': info['user'],
        'DB_PASSWORD': info['password'],
        'DB_TYPE': 'postgresql',
        'DB_ECHO': 'false',
        'PYTHONPATH': str(BACKEND / 'src'),
        'PYTHON_DOTENV_DISABLED': '1',
    }
    for suffix in ('HOST', 'PORT', 'DATABASE', 'USERNAME', 'PASSWORD', 'TYPE', 'ECHO'):
        env['INSIGHTHUB_DB_' + suffix] = env['DB_' + suffix]
    os.environ.update(
        {key: value for key, value in env.items() if key.startswith(('DB_', 'INSIGHTHUB_', 'PYTHON_DOTENV'))}
    )
    sys.path.insert(0, str(BACKEND / 'src'))
    # Actual asyncpg transactional rollback before the committed CLI migration.
    verify_code_unchanged()
    asyncio.run(actual_rollback(info, root, manifest, corrupt=True))
    asyncio.run(actual_rollback(info, root, manifest, corrupt=False))
    verify_code_unchanged()
    result = subprocess.run(
        [sys.executable, '-m', 'alembic', '-x', f'numeric_backup={root}', 'upgrade', '20261025_numeric_business_ids'],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        timeout=60,
        check=False,
    )
    diagnostic = (result.stdout + result.stderr).decode(errors='replace').replace(info['password'], '[REDACTED]')
    (root / 'alembic.log').write_text(diagnostic)
    os.chmod(root / 'alembic.log', 0o600)
    assert result.returncode == 0, diagnostic[-5000:]
    report = verify(info, root, fixture)
    report.update(asyncio.run(actual_queue_replay(info, root)))
    verify_code_unchanged()
    report.update(
        database=database,
        evidence=str(root / 'verification.json'),
        driver='asyncpg',
        actual_savepoint_failure_rollback='passed',
        actual_outer_transaction_rollback='passed',
        consistent_utc_backup=True,
        no_existing_database_reset=True,
        no_live_database_connected=True,
        started_at_utc=started_at,
        completed_at_utc=datetime.now(timezone.utc).isoformat(),
        production_module_sha256=production_hashes['backend/src/app/numeric_id_migration.py'],
        production_sha256=production_hashes,
        production_code_unchanged=True,
    )
    private_json(root / 'verification.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
