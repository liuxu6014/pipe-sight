"""Offline migration planning and read-only inspection, never the app database."""

import hashlib
import json
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.entrypoints import safe_migrate as module

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED', '1')

    def reject(*_args, **_kwargs):
        raise AssertionError('Deployment planning tests must not contact a real database')

    monkeypatch.setattr(socket, 'create_connection', reject)
    monkeypatch.setattr(socket.socket, 'connect', reject)


@pytest.fixture
def script():
    return ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))


def private_json(path, value):
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path


def backup(root, source):
    root.mkdir(mode=0o700)
    dump = root / 'database-before.dump'
    dump.write_bytes(b'synthetic dump sentinel; never restored')
    dump.chmod(0o600)
    private_json(
        root / 'database-before.json',
        {
            'revision': source,
            'sha256': hashlib.sha256(dump.read_bytes()).hexdigest(),
            'tables': ['synthetic'],
            'fingerprints': {'synthetic': [1, 'sentinel']},
        },
    )
    return root


def options(root, source, target, values):
    return private_json(
        root / 'options.json', {'source_revision': source, 'target_revision': target, 'x_arguments': values}
    )


def test_empty_and_unversioned_databases_are_not_bootstrapped():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        with pytest.raises(module.MigrationSafetyError, match='不会自动建库或 stamp'):
            module.inspect_revision(connection)
        connection.execute(text('CREATE TABLE original (id integer PRIMARY KEY)'))
        with pytest.raises(module.MigrationSafetyError):
            module.inspect_revision(connection)
        assert {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))} == {
            'original'
        }


def test_read_revision_rejects_empty_or_branched_version_records():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE alembic_version (version_num text)'))
        with pytest.raises(module.MigrationSafetyError):
            module.inspect_revision(connection)
        connection.execute(text("INSERT INTO alembic_version VALUES ('first')"))
        assert module.inspect_revision(connection) == 'first'
        connection.execute(text("INSERT INTO alembic_version VALUES ('second')"))
        with pytest.raises(module.MigrationSafetyError):
            module.inspect_revision(connection)


def test_head_is_noop_and_ordinary_forward_upgrade_needs_no_historical_overrides(script):
    head = script.get_heads()[0]
    assert module.migration_command(script, source=head, target='head', options_file=None, root=ROOT) == (None, head)
    previous = script.get_revision(head).down_revision
    command, destination = module.migration_command(
        script, source=previous, target='head', options_file=None, root=ROOT
    )
    assert command[-2:] == ['upgrade', head]
    assert '-x' not in command and destination == head


@pytest.mark.parametrize(
    'source',
    [
        '20261025_retire_processing_views',
        '20261025_compact_schema',
        '20261025_restore_ruoyi_names',
        '20261025_numeric_business_ids',
        '20261025_business_consistency',
    ],
)
def test_default_head_does_not_cross_historical_backups(script, source):
    with pytest.raises(module.MigrationSafetyError, match='分阶段备份'):
        module.migration_command(script, source=source, target='head', options_file=None, root=ROOT)


def test_verified_single_historical_step_passes_original_x_options(script, tmp_path):
    source, target = '20261025_compact_schema', '20261025_restore_ruoyi_names'
    folder = backup(tmp_path / 'ruoyi', source)
    plan = options(tmp_path, source, target, {'ruoyi_backup': str(folder), 'ruoyi_allow_live': 'true'})
    command, destination = module.migration_command(script, source=source, target=target, options_file=plan, root=ROOT)
    assert command[-2:] == ['upgrade', target] and destination == target
    assert command[command.index('-x') + 1] == 'ruoyi_allow_live=true'
    assert f'ruoyi_backup={folder}' in command
    # Never turn an explicit staged request into head or add bypass flags.
    assert command.count('-x') == 2 and 'stamp' not in command


def test_historical_plan_cannot_skip_multiple_backup_boundaries(script, tmp_path):
    source, target = '20261025_compact_schema', '20261025_numeric_business_ids'
    plan = options(tmp_path, source, target, {'numeric_backup': str(tmp_path)})
    with pytest.raises(module.MigrationSafetyError, match='分阶段备份'):
        module.migration_command(script, source=source, target=target, options_file=plan, root=ROOT)


@pytest.mark.parametrize('problem', ['dump', 'revision', 'public', 'unknown-option', 'target'])
def test_historical_materials_fail_closed(script, tmp_path, problem):
    source, target = '20261025_compact_schema', '20261025_restore_ruoyi_names'
    folder = backup(tmp_path / 'ruoyi', source)
    values = {'ruoyi_backup': str(folder)}
    if problem == 'dump':
        (folder / 'database-before.dump').write_bytes(b'changed')
    elif problem == 'revision':
        private_json(folder / 'database-before.json', {'revision': 'wrong'})
    elif problem == 'public':
        folder.chmod(0o755)
    elif problem == 'unknown-option':
        values['disable_safety'] = 'true'
    plan = options(tmp_path, source, target if problem != 'target' else 'head', values)
    with pytest.raises(module.MigrationSafetyError):
        module.migration_command(script, source=source, target=target, options_file=plan, root=ROOT)


def test_missing_backup_and_downgrade_are_rejected(script):
    with pytest.raises(module.MigrationSafetyError):
        module.migration_command(
            script, source=script.get_heads()[0], target='20261025_compact_schema', options_file=None, root=ROOT
        )
    with pytest.raises(module.MigrationSafetyError):
        module.migration_command(script, source='unknown', target='head', options_file=None, root=ROOT)


def test_early_ordinary_history_cannot_bypass_controlled_rollout(script):
    with pytest.raises(module.MigrationSafetyError, match='较早历史版本'):
        module.migration_command(
            script,
            source='20260829_drop_legacy_tables',
            target='20261002_content_review_workflow',
            options_file=None,
            root=ROOT,
        )


@pytest.mark.asyncio
async def test_runtime_head_inspection_does_not_launch_alembic(script, monkeypatch):
    head = script.get_heads()[0]
    monkeypatch.setattr(module, 'current_revision', AsyncMock(return_value=head))
    invoked = []
    monkeypatch.setattr(module.subprocess, 'run', lambda *_args, **_kwargs: invoked.append(True))
    await module.migrate(target='head', options_file=None, root=ROOT)
    assert invoked == []


@pytest.mark.asyncio
async def test_runtime_checks_version_after_success_and_disables_dotenv(script, monkeypatch):
    head = script.get_heads()[0]
    previous = script.get_revision(head).down_revision
    monkeypatch.setattr(module, 'current_revision', AsyncMock(side_effect=[previous, head]))
    invoked = []

    def run(command, **kwargs):
        invoked.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, 'run', run)
    await module.migrate(target='head', options_file=None, root=ROOT)
    assert invoked[0][1]['env']['PYTHON_DOTENV_DISABLED'] == '1'
    assert invoked[0][1]['env']['DB_ECHO'] == 'false'
    assert invoked[0][1]['env']['PIPESIGHT_EXPECTED_SOURCE_REVISION'] == previous
    assert invoked[0][0][-2:] == ['upgrade', head]


@pytest.mark.asyncio
async def test_runtime_failure_does_not_claim_completion(script, monkeypatch):
    head = script.get_heads()[0]
    previous = script.get_revision(head).down_revision
    monkeypatch.setattr(module, 'current_revision', AsyncMock(return_value=previous))
    monkeypatch.setattr(module.subprocess, 'run', lambda *_args, **_kwargs: SimpleNamespace(returncode=1))
    with pytest.raises(module.MigrationSafetyError, match='API/Worker 不应启动'):
        await module.migrate(target='head', options_file=None, root=ROOT)


@pytest.mark.asyncio
async def test_connection_settings_must_be_explicit_without_reading_env_files(monkeypatch):
    for name in ('DB_HOST', 'DB_PORT', 'DB_DATABASE', 'DB_USERNAME', 'DB_PASSWORD'):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(module.MigrationSafetyError, match=r'不读取 \.env'):
        await module.current_revision()
