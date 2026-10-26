"""Offline scheduler behavior and personal-chat retirement checks."""

# ruff: noqa: ANN001, ANN201, ANN202, PLR2004

import ast
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import tomllib

from app.infrastructure.models.jobs import SysJob
from config import get_scheduler as scheduling


@pytest.fixture(autouse=True)
def no_connections(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No real database, Redis, or network connections allowed')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


def canonical_job(**overrides):
    values = {
        'id': 17,
        'name': 'canonical task',
        'group_key': 'default',
        'executor': 'processpool',
        'invoke_target': 'builtins.print',
        'args': 'one,two',
        'kwargs': '{"sep":"/"}',
        'cron_expression': '0 0 8 * * ?',
        'misfire_policy': '2',
        'concurrent': '1',
        'status': '0',
        'created_at': datetime(2026, 10, 24, 8),
        'updated_at': datetime(2026, 10, 25, 8),
    }
    values.update(overrides)
    return SysJob(**values)


def test_scheduler_accepts_canonical_row_and_existing_dto():
    row = canonical_job()
    dto = scheduling.SchedulerUtil._job_to_dto(row)
    assert dto.job_id == row.id
    assert dto.job_name == row.name
    assert dto.update_time == row.updated_at
    assert dto.model_dump(by_alias=True)['jobGroup'] == 'default'
    assert scheduling.SchedulerUtil._job_to_dto(dto) is dto
    for source in (row, dto):
        config = scheduling.SchedulerUtil._prepare_scheduler_job_add(source)
        assert config['id'] == '17'
        assert config['name'] == row.name
        assert config['args'] == ['one', 'two']
        assert config['kwargs'] == {'sep': '/'}
        assert config['executor'] == 'processpool'
        assert config['coalesce'] is True


@pytest.mark.asyncio
async def test_scheduler_sync_add_update_remove_with_canonical_rows(monkeypatch):
    util = scheduling.SchedulerUtil
    job = canonical_job()
    scheduler = MagicMock()
    scheduler.get_job.return_value = None
    scheduler.get_jobs.return_value = [SimpleNamespace(id='18'), SimpleNamespace(id='_internal')]
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(util, '_is_leader', True)
    monkeypatch.setattr(util, '_job_update_time_cache', {})
    monkeypatch.setattr(util, '_get_sync_async_session', lambda: session)
    monkeypatch.setattr(scheduling, 'scheduler', scheduler)
    monkeypatch.setattr(scheduling.JobDao, 'get_all_job_list_for_scheduler', AsyncMock(return_value=[job]))
    await util._sync_jobs_from_database()
    scheduler.remove_job.assert_called_once_with(job_id='18')
    assert scheduler.add_job.call_args.kwargs['id'] == '17'
    assert util._job_update_time_cache == {'17': job.updated_at}

    scheduler.reset_mock()
    scheduler.get_jobs.return_value = [SimpleNamespace(id='17')]
    job.updated_at = datetime(2026, 10, 25, 9)
    monkeypatch.setattr(util, '_is_job_config_in_sync', lambda *args: False)
    await util._sync_jobs_from_database()
    scheduler.remove_job.assert_called_once_with(job_id='17')
    assert scheduler.add_job.call_args.kwargs['id'] == '17'
    assert util._job_update_time_cache['17'] == job.updated_at


def test_scheduler_direct_log_uses_dto_and_job_fk(monkeypatch):
    session = MagicMock()
    log_service = MagicMock()
    monkeypatch.setattr(scheduling.SchedulerUtil, '_get_session_local', lambda: lambda: session)
    monkeypatch.setattr(scheduling.JobLogService, 'add_job_log_services', log_service)
    scheduling.SchedulerUtil._record_job_execution_log(canonical_job(), 'default', '1', 'failure')
    log = log_service.call_args.args[1]
    assert log.job_id == 17
    assert log.job_name == 'canonical task'
    assert log.exception_info == 'failure'
    assert log.create_time is not None
    session.close.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_start_registers_collection_and_research_only(monkeypatch):
    util = scheduling.SchedulerUtil
    scheduler = MagicMock()
    collection = AsyncMock()
    research = MagicMock()
    exports = MagicMock()
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(scheduling, 'scheduler', scheduler)
    monkeypatch.setattr(util, '_configure_scheduler', lambda: None)
    monkeypatch.setattr(util, '_get_sync_async_session', lambda: session)
    monkeypatch.setattr(util, '_should_enable_scheduler_sync', lambda: False)
    monkeypatch.setattr(util, '_is_leader', False)
    monkeypatch.setattr(util, '_disposed_sync_engines', True)
    monkeypatch.setattr(scheduling.AppConfig, 'pipeline_task_scheduler_enabled', True)
    monkeypatch.setattr(scheduling, 'register_real_collection_schedules', collection)
    monkeypatch.setattr(scheduling, 'register_research_job_recovery', research)
    monkeypatch.setattr(scheduling, 'register_report_export_recovery', exports)
    monkeypatch.setattr(scheduling.JobDao, 'get_job_list_for_scheduler', AsyncMock(return_value=[canonical_job()]))
    await util._start_scheduler_as_leader(MagicMock())
    collection.assert_awaited_once_with(scheduler)
    research.assert_called_once_with(scheduler)
    exports.assert_called_once_with(scheduler)
    assert scheduler.add_job.call_args.kwargs['id'] == '17'
    assert not hasattr(scheduling, 'register_insighthub_handoff_polling')


BACKEND_ROOT = Path(__file__).resolve().parents[1]
RETIRED_CHAT_MODULES = (
    'app.intelligence.models.ai_chat',
    'app.intelligence.repositories.ai_chat_repository',
    'app.intelligence.services.ai_chat_service',
    'app.intelligence.schemas.ai_chat',
    'app.intelligence.api.ai_chat_controller',
    'app.intelligence.services.model_provider',
)
CHAT_FRAMEWORK_TABLES = {
    'chat_settings',
    'ai_chat_config',
    'ai_sessions',
    'ai_memories',
    'ai_metrics',
    'ai_eval_runs',
    'ai_knowledge',
    'ai_culture',
    'ai_traces',
    'ai_spans',
    'ai_schema_versions',
}


@pytest.mark.parametrize('module_name', RETIRED_CHAT_MODULES)
def test_personal_chat_module_source_is_removed(module_name):
    assert not (BACKEND_ROOT / 'src' / (module_name.replace('.', '/') + '.py')).exists()


def test_runtime_scripts_and_cli_do_not_import_personal_chat_or_agno():
    roots = (BACKEND_ROOT / 'src', BACKEND_ROOT / 'cli', BACKEND_ROOT / 'scripts', BACKEND_ROOT.parent / 'scripts')
    for root in roots:
        for path in root.rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ''
                    names = [base, *(f'{base}.{alias.name}' for alias in node.names)]
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    names = [node.value]  # Dynamic import_module registry names.
                assert not any(
                    name in RETIRED_CHAT_MODULES or name == 'agno' or name.startswith('agno.') for name in names
                ), (path, node.lineno)


def test_chat_framework_dependency_is_removed():
    project = tomllib.loads((BACKEND_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    assert not any(dependency.lower().startswith('agno') for dependency in project['project']['dependencies'])
    for filename in ('requirements.txt', 'requirements-pg.txt'):
        assert not any(line.lower().startswith('agno') for line in (BACKEND_ROOT / filename).read_text().splitlines())


def test_api_import_has_no_chat_routes_or_framework_tables():
    # Run in a clean interpreter so old metadata/import state cannot hide leaks.
    source = f"""
import socket
def forbidden(*args, **kwargs):
    raise AssertionError('No external connections')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from app.bootstrap import create_app
from config.database import Base
app = create_app()
assert not any(route.path.startswith('/ai/chat') for route in app.routes)
assert not set({CHAT_FRAMEWORK_TABLES!r}) & set(Base.metadata.tables)
assert len(Base.metadata.tables) == 27
import sys
assert not any(name == 'agno' or name.startswith('agno.') for name in sys.modules)
assert not any(name in sys.modules for name in {RETIRED_CHAT_MODULES!r})
from app.intelligence.services.ai_model_service import AiModelService
from app.research.services.model_generation import ModelGateway
assert callable(AiModelService.get_ai_model_list_services)
assert callable(ModelGateway.call)
"""
    result = subprocess.run(
        [sys.executable, '-c', source], cwd=BACKEND_ROOT, capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
