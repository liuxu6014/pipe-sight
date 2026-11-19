"""The comment-only entry point keeps the real PG rehearsal's safety boundaries."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def runner():
    path = Path(__file__).parents[1] / 'scripts/run_pg_rehearsals.py'
    spec = importlib.util.spec_from_file_location('pg_rehearsal_runner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def manifest(tmp_path):
    data = {
        'connection': {
            'host': '127.0.0.1',
            'port': 19432,
            'dbname': 'pipesight_rehearsal',
            'user': 'unit_test',
            'password': 'unit-test-only',
        },
        'legacy_database': 'pipesight_compact_pgtest_123456abcdef',
        'current_database': 'pipesight_beijing_pgtest_123456abcdef',
        'evidence_root': str(tmp_path),
        'numeric_seed_backup': str(tmp_path / 'numeric_backup'),
        'snapshot_root': str(tmp_path / 'snapshot'),
    }
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(data))
    return path


@pytest.mark.parametrize('comments_only', [False, True])
def test_runner_selects_the_actual_comment_test_and_backs_up_before_running(
    runner, manifest, monkeypatch, comments_only
):
    events = []
    monkeypatch.setattr(runner, 'validate', lambda info: events.append('validated'))
    monkeypatch.setattr(runner, 'backup', lambda *args: events.append('backup'))

    def execute(command, *, cwd, env, check):
        events.append('pytest')
        assert cwd == runner.BACKEND and check is False
        assert command[3] == (
            'tests/test_application_schema_comments.py::test_comment_only_pg18_updates_preserve_every_business_row'
            if comments_only
            else 'tests'
        )
        assert env['PIPESIGHT_COMPACT_COMMENT_REHEARSE'] == '1'
        assert env['PIPESIGHT_PG_REHEARSAL_MANIFEST'] == str(manifest)
        assert env['PYTHON_DOTENV_DISABLED'] == '1'
        assert env['DB_DATABASE'] == 'pipesight_beijing_pgtest_123456abcdef'
        assert env['DB_PORT'] == '19432'
        assert env['INSIGHTHUB_DB_DATABASE'] == env['DB_DATABASE']
        report = Path(next(arg.split('=', 1)[1] for arg in command if arg.startswith('--junitxml=')))
        assert report.name == ('pytest-comments.xml' if comments_only else 'pytest.xml')
        report.write_text('<testsuites><testsuite tests="1" skipped="0" failures="0" errors="0" /></testsuites>')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, 'run', execute)
    assert runner.run(manifest, comments_only=comments_only) == 0
    assert events == (['validated', 'backup', 'pytest'] if comments_only else ['validated', 'pytest'])


@pytest.mark.parametrize('exit_code,skipped', [(1, 0), (0, 1)])
def test_comment_runner_does_not_accept_failed_or_skipped_tests(runner, manifest, monkeypatch, exit_code, skipped):
    monkeypatch.setattr(runner, 'validate', lambda info: None)
    monkeypatch.setattr(runner, 'backup', lambda *args: None)

    def execute(*args, **kwargs):
        (manifest.parent / 'pytest-comments.xml').write_text(
            f'<testsuites><testsuite tests="1" skipped="{skipped}" /></testsuites>'
        )
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(runner.subprocess, 'run', execute)
    if exit_code:
        assert runner.run(manifest, comments_only=True) == exit_code
    else:
        with pytest.raises(RuntimeError, match='zero skips'):
            runner.run(manifest, comments_only=True)


@pytest.mark.parametrize(
    'field,value',
    [
        ('current_database', 'pipesight'),
        ('legacy_database', 'pipesight'),
        ('current_database', 'pipesight_compact_pgtest_123456abcdef'),
        ('current_database', 'pipesight_beijing_pgtest_123456abcdef;DROP DATABASE pipesight'),
    ],
)
def test_runner_rejects_non_disposable_database_before_any_connection(runner, manifest, monkeypatch, field, value):
    data = json.loads(manifest.read_text())
    data[field] = value
    manifest.write_text(json.dumps(data))
    validate, backup, execute = Mock(), Mock(), Mock()
    monkeypatch.setattr(runner, 'validate', validate)
    monkeypatch.setattr(runner, 'backup', backup)
    monkeypatch.setattr(runner.subprocess, 'run', execute)
    with pytest.raises(ValueError, match='Invalid isolated rehearsal database'):
        runner.run(manifest, comments_only=True)
    validate.assert_not_called()
    backup.assert_not_called()
    execute.assert_not_called()


def test_comment_runner_requires_a_successful_backup(runner, manifest, monkeypatch):
    execute = Mock()
    monkeypatch.setattr(runner, 'validate', lambda info: None)
    monkeypatch.setattr(runner, 'backup', Mock(side_effect=RuntimeError('backup failed')))
    monkeypatch.setattr(runner.subprocess, 'run', execute)
    with pytest.raises(RuntimeError, match='backup failed'):
        runner.run(manifest, comments_only=True)
    execute.assert_not_called()


@pytest.mark.parametrize('comments_only', [False, True])
def test_cli_only_requires_pdf_fixtures_for_full_regression(runner, manifest, monkeypatch, comments_only):
    pdf, execute = Mock(), Mock(return_value=0)
    monkeypatch.setattr(runner, 'validate_pdf_fixtures', pdf)
    monkeypatch.setattr(runner, 'run', execute)
    args = ['run_pg_rehearsals.py', '--manifest', str(manifest)]
    if comments_only:
        args.append('--comments-only')
    monkeypatch.setattr(runner.sys, 'argv', args)
    assert runner.main() == 0
    assert pdf.call_count == (0 if comments_only else 1)
    execute.assert_called_once_with(manifest.resolve(), comments_only=comments_only)
