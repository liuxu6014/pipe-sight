"""Prepare separate legacy/current PG18 databases, then run every opt-in test.

Requires the private legacy dump/manifest and the labelled localhost container.
Never drops a database, restores over existing data, or reads application .env.
Run with backend/.venv/bin/python; see docs/pg-rehearsal.md.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

import psycopg2
from psycopg2 import sql

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
CONTAINER = 'pipesight-schema-rehearsal-ythnjxpi'


def validate_pdf_fixtures() -> None:
    if importlib.util.find_spec('pymupdf') is None:
        raise RuntimeError('Install the locked dev dependencies first: uv sync --project backend --group dev --locked')
    records = json.loads((BACKEND / 'data/curated/paper-fulltext-previews.json').read_text())['records']
    for doi, filename in (
        ('10.3390/coatings14030358', 'coatings-14-00358.pdf'),
        ('10.6047/j.issn.1000-8241.2024.03.001', 'pipeline-inspection-review-2024.pdf'),
    ):
        path = ROOT / 'output/pdf/paper-fulltext-20261017' / filename
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != records[doi]['sha256']:
            raise RuntimeError(f'Missing or changed original PDF fixture: {path}; see docs/pg-rehearsal.md')


def docker(*args, payload=None) -> bytes:
    return subprocess.run(['docker', *args], input=payload, check=True, capture_output=True, timeout=120).stdout


def private_json(path, value) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def validate(info) -> None:
    assert (info['host'], info['port'], info['dbname']) == ('127.0.0.1', 19432, 'pipesight_rehearsal')
    labels = json.loads(docker('inspect', '--format', '{{json .Config.Labels}}', CONTAINER))
    ports = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', CONTAINER))
    assert labels['pipesight.schema-rollout'] == 'ythNjXpI'
    assert {'HostIp': '127.0.0.1', 'HostPort': '19432'} in ports['5432/tcp']


def backup(info, database, folder) -> None:
    folder.mkdir(mode=0o700)
    with psycopg2.connect(**{**info, 'dbname': database}) as db:
        db.set_session(isolation_level='REPEATABLE READ', readonly=True)
        with db.cursor() as cursor:
            cursor.execute("SET LOCAL TIME ZONE 'UTC'")
            cursor.execute('SELECT pg_export_snapshot()')
            snapshot = cursor.fetchone()[0]
            cursor.execute('SELECT version_num FROM alembic_version')
            revision = cursor.fetchone()[0]
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
            tables = [row[0] for row in cursor.fetchall()]
            fingerprints = {}
            for table in tables:
                cursor.execute(
                    sql.SQL(
                        "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
                        '(SELECT md5(row_to_json(t)::text) h FROM public.{} t)s'
                    ).format(sql.Identifier(table))
                )
                fingerprints[table] = list(cursor.fetchone())
            dump = docker(
                'exec', CONTAINER, 'pg_dump', '-U', info['user'], '-d', database, '-Fc', '--snapshot', snapshot
            )
            path = folder / 'database-before.dump'
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
                stream.write(dump)
            private_json(
                folder / 'database-before.json',
                {
                    'revision': revision,
                    'tables': tables,
                    'fingerprints': fingerprints,
                    'sha256': hashlib.sha256(dump).hexdigest(),
                    'fingerprint_timezone': 'UTC',
                },
            )


def environment(info, database) -> dict:
    env = {**os.environ, 'PYTHON_DOTENV_DISABLED': '1', 'PYTHONPATH': str(BACKEND / 'src')}
    values = {
        'HOST': '127.0.0.1',
        'PORT': '19432',
        'DATABASE': database,
        'USERNAME': info['user'],
        'PASSWORD': info['password'],
        'TYPE': 'postgresql',
        'ECHO': 'false',
    }
    for prefix in ('DB_', 'INSIGHTHUB_DB_'):
        env.update({prefix + key: value for key, value in values.items()})
    return env


def upgrade(info, database, revision, folder, **options) -> None:
    command = [sys.executable, '-m', 'alembic', '-c', 'alembic.ini']
    for key, value in options.items():
        command += ['-x', f'{key}={value}']
    result = subprocess.run(
        [*command, 'upgrade', revision],
        cwd=BACKEND,
        env=environment(info, database),
        capture_output=True,
        timeout=180,
        check=False,
    )
    diagnostic = (result.stdout + result.stderr).decode(errors='replace').replace(info['password'], '[REDACTED]')
    (folder / f'{revision}.log').write_text(diagnostic)
    if result.returncode:
        raise RuntimeError(diagnostic[-5000:])


def prepare(args) -> Path:
    info = json.loads(args.connection_file.read_text())
    validate(info)
    source = json.loads((args.snapshot_dir / 'database-before.json').read_text())
    dump = (args.snapshot_dir / 'database-before.dump').read_bytes()
    assert hashlib.sha256(dump).hexdigest() == source['sha256']
    root = args.evidence_dir.resolve() / ('run-' + uuid4().hex[:12])
    root.mkdir(parents=True, mode=0o700)
    suffix = uuid4().hex[:12]
    legacy = 'pipesight_compact_pgtest_' + suffix
    current = 'pipesight_beijing_pgtest_' + suffix
    # createdb fails on collisions; existing databases are never modified.
    for database in (legacy, current):
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
            payload=dump,
        )
    # Plan the actual historical CLI migration on the restored 47-table source.
    os.environ.update(environment(info, current))
    sys.path.insert(0, str(BACKEND / 'src'))
    import sqlalchemy as sa

    from app import schema_migration

    engine = sa.create_engine(
        sa.URL.create(
            'postgresql+psycopg2',
            username=info['user'],
            password=info['password'],
            host=info['host'],
            port=info['port'],
            database=current,
        ),
        hide_parameters=True,
    )
    try:
        with engine.connect() as bind:
            schema_migration.verify_source_snapshot(bind, source, allow_live=True)
            plan = schema_migration.preflight(bind, historical_timezone='Asia/Shanghai', allow_live=True)
            archive = root / 'retirement.json'
            digest = schema_migration.archive_plan(plan, archive)
    finally:
        engine.dispose()
    upgrade(
        info,
        current,
        '20261025_compact_schema',
        root,
        compact_archive=archive,
        compact_archive_sha256=digest,
        compact_source_snapshot=args.snapshot_dir / 'database-before.json',
        historical_timezone='Asia/Shanghai',
        compact_allow_live='true',
    )
    for revision, key in (
        ('20261025_restore_ruoyi_names', 'ruoyi_backup'),
        ('20261025_numeric_business_ids', 'numeric_backup'),
        ('20261025_business_consistency', 'business_backup'),
        ('20261025_beijing_audit_time', 'beijing_backup'),
    ):
        folder = root / key
        backup(info, current, folder)
        upgrade(info, current, revision, root, **{key: folder})
    upgrade(info, current, 'head', root)
    path = root / 'manifest.json'
    private_json(
        path,
        {
            'connection': info,
            'legacy_database': legacy,
            'current_database': current,
            'snapshot_root': str(args.snapshot_dir.resolve()),
            'evidence_root': str(root),
            'numeric_seed_backup': str(root / 'numeric_backup'),
        },
    )
    print(f'Prepared isolated legacy/current databases; manifest: {path}', flush=True)
    return path


def run(path, *, comments_only=False) -> int:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    manifest = json.loads(path.read_text())
    info = manifest['connection']
    for key, prefix in (('legacy_database', 'compact'), ('current_database', 'beijing')):
        if not re.fullmatch(rf'pipesight_{prefix}_pgtest_[a-f0-9]{{12}}', manifest[key]):
            raise ValueError(f'Invalid isolated rehearsal database: {key}')
    validate(info)
    if comments_only:
        backup(
            info,
            manifest['current_database'],
            Path(manifest['evidence_root']) / ('comments-backup-' + uuid4().hex[:12]),
        )
    env = environment(info, manifest['current_database'])
    config = Config(str(BACKEND / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND / 'alembic'))
    env.update(
        dict.fromkeys(
            (
                'PIPESIGHT_COMPACT_REHEARSE',
                'PIPESIGHT_ASYNCPG_ALEMBIC_REHEARSE',
                'PIPESIGHT_SEEDED_NUMERIC_REHEARSE',
                'PIPESIGHT_COLLECTION_PG18',
                'PIPESIGHT_TIME_PARSECAS_REHEARSE',
                'PIPESIGHT_REPORT_METADATA_PG',
                'PIPESIGHT_COMPACT_COMMENT_REHEARSE',
                'PIPESIGHT_PAGINATION_PG_REHEARSE',
            ),
            '1',
        )
    )
    env.update(
        PIPESIGHT_PG_REHEARSAL_MANIFEST=str(path),
        PIPESIGHT_FIELD_REPAIR_REVISION=ScriptDirectory.from_config(config).get_current_head(),
        PIPESIGHT_NUMERIC_SEED_BACKUP=manifest['numeric_seed_backup'],
        PIPESIGHT_PG_EVIDENCE=manifest['evidence_root'],
        PIPESIGHT_PG_SNAPSHOT_ROOT=manifest['snapshot_root'],
    )
    report = Path(manifest['evidence_root']) / ('pytest-comments.xml' if comments_only else 'pytest.xml')
    target = (
        'tests/test_application_schema_comments.py::test_comment_only_pg18_updates_preserve_every_business_row'
        if comments_only
        else 'tests'
    )
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', target, '-q', '--tb=short', f'--junitxml={report}'],
        cwd=BACKEND,
        env=env,
        check=False,
    )
    if result.returncode:
        return result.returncode
    suites = ET.parse(report).getroot().iter('testsuite')
    skipped = sum(int(suite.get('skipped', '0')) for suite in suites)
    if skipped:
        raise RuntimeError(f'Full PG acceptance requires zero skips; found {skipped}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-dir', type=Path, default=ROOT / '.runtime/schema-rollout-ythNjXpI')
    parser.add_argument(
        '--connection-file', type=Path, default=ROOT / '.runtime/schema-rollout-ythNjXpI/rehearsal-connection.json'
    )
    parser.add_argument('--evidence-dir', type=Path, default=ROOT / '.runtime/pg-acceptance')
    parser.add_argument('--manifest', type=Path, help='Reuse an already prepared isolated environment')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument(
        '--comments-only', action='store_true', help='Run the comment-only PG18 rehearsal without PDF fixtures'
    )
    args = parser.parse_args()
    if not args.comments_only:
        validate_pdf_fixtures()
    path = args.manifest.resolve() if args.manifest else prepare(args)
    return 0 if args.prepare_only else run(path, comments_only=args.comments_only)


if __name__ == '__main__':
    raise SystemExit(main())
