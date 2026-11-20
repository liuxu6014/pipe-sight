"""Behavior checks for scanner framing, heartbeat and deployment fail-closed checks."""

import asyncio
import json
import socket
import struct
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from app.entrypoints import runtime_check
from app.entrypoints.file_scan import scan_file
from app.health import worker
from app.health.api import controller


def test_api_and_worker_startup_imports_are_complete():
    result = subprocess.run(
        [sys.executable, '-c', 'import app.bootstrap; import app.entrypoints.task_worker'],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    'reply,expected',
    [
        (b'stream: OK\0', 0),
        (b'stream: Eicar-Test-Signature FOUND\0', 1),
        (b'stream: limit exceeded ERROR\0', 2),
        (b'\0', 2),
    ],
)
def test_scanner_streams_actual_bytes_and_fails_closed(tmp_path, reply, expected):
    content = b'Synthetic upload\0with binary bytes' * 4096
    path = tmp_path / 'source.bin'
    path.write_bytes(content)
    received = []
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0))
        server.listen()
        server.settimeout(5)

        def serve():
            with server.accept()[0] as client:
                client.settimeout(5)
                command = bytearray()
                while not command.endswith(b'\0'):
                    command.extend(client.recv(1))
                assert command == b'zINSTREAM\0'

                def read_exact(size):
                    data = bytearray()
                    while len(data) < size:
                        chunk = client.recv(size - len(data))
                        if not chunk:
                            raise AssertionError('Truncated scan stream')
                        data.extend(chunk)
                    return data

                while size := struct.unpack('!I', read_exact(4))[0]:
                    received.extend(read_exact(size))
                client.sendall(reply)

        thread = threading.Thread(target=serve)
        thread.start()
        code, _ = scan_file(path, host='127.0.0.1', port=server.getsockname()[1], timeout=2)
        thread.join(5)
    assert not thread.is_alive()
    assert code == expected
    assert bytes(received) == content


def test_worker_heartbeat_missing_stale_and_future_are_unhealthy(tmp_path):
    path = tmp_path / 'heartbeat.json'
    assert worker.worker_status(path=path)['status'] == 'unavailable'
    for stamp in (0, 106, None, 'bad'):
        path.write_text(json.dumps({'at': stamp, 'status': 'running'}))
        assert worker.worker_status(path=path, now=100)['status'] == 'unavailable'
    queues = {name: {'ok': True, 'lastSuccess': 95} for name in worker.EXPECTED_QUEUES}
    path.write_text(json.dumps({'at': 95, 'status': 'running', 'queues': queues}))
    assert worker.worker_status(path=path, now=100) == {'status': 'ok', 'lastSeenSeconds': 5}


@pytest.mark.asyncio
async def test_worker_heartbeat_updates_and_removes_on_shutdown(tmp_path, monkeypatch):
    path = tmp_path / 'heartbeat.json'
    monkeypatch.setenv('TASK_WORKER_HEARTBEAT_PATH', str(path))
    monkeypatch.setattr(worker, '_queue_scans', {})
    for name in worker.EXPECTED_QUEUES:
        worker.queue_scan_result(name, success=True)
    stop = asyncio.Event()
    task = asyncio.create_task(worker.run_worker_heartbeat(stop))
    await asyncio.sleep(0)
    assert worker.worker_status()['status'] == 'ok'
    response = await controller.health_worker()
    assert response.status_code == 200
    stop.set()
    await task
    assert not path.exists()
    response = await controller.health_worker()
    assert response.status_code == 503


@pytest.mark.parametrize('bad_queue', ['failed', 'stale', 'future', 'missing', 'invalid', 'nan'])
def test_fresh_heartbeat_requires_fresh_successful_queue_scans(tmp_path, bad_queue):
    path = tmp_path / 'heartbeat.json'
    queues = {name: {'ok': True, 'lastSuccess': 200} for name in worker.EXPECTED_QUEUES}
    queues['research'] = {
        'failed': {'ok': False, 'lastSuccess': 200},
        'stale': {'ok': True, 'lastSuccess': 1},
        'future': {'ok': True, 'lastSuccess': 208},
        'missing': {},
        'invalid': {'ok': True, 'lastSuccess': None},
        'nan': {'ok': True, 'lastSuccess': float('nan')},
    }[bad_queue]
    path.write_text(json.dumps({'at': 200, 'status': 'running', 'queues': queues}))
    assert worker.worker_status(path=path, now=201) == {
        'status': 'unavailable',
        'reason': 'queue_scan_failed',
        'queues': ['research'],
    }


def test_heartbeat_without_queue_evidence_is_not_healthy(tmp_path):
    path = tmp_path / 'heartbeat.json'
    path.write_text(json.dumps({'at': 100, 'status': 'running'}))
    assert worker.worker_status(path=path, now=100)['status'] == 'unavailable'


@pytest.mark.asyncio
async def test_research_queue_failure_does_not_skip_other_scans(monkeypatch):
    from unittest.mock import AsyncMock

    from app.research.tasks import research_job_scheduler as scheduler

    stop = asyncio.Event()
    statuses = {}
    monkeypatch.setattr(scheduler, 'queue_scan_result', lambda name, *, success: statuses.update({name: success}))
    monkeypatch.setattr(scheduler, 'recover_research_jobs', AsyncMock(side_effect=RuntimeError('simulated failure')))
    for name in (
        'recover_report_exports',
        'dispatch_digest_schedules',
        'recover_material_parses',
        'stop_recovery_tasks',
    ):
        monkeypatch.setattr(scheduler, name, AsyncMock())
    monkeypatch.setattr(scheduler, 'clean_deleted_report_files', AsyncMock(side_effect=stop.set))
    await asyncio.wait_for(scheduler.run_persistent_recovery_loop(stop), timeout=1)
    assert statuses == {'research': False, 'exports': True, 'digest': True, 'materials': True, 'export_cleanup': True}


def test_production_preflight_rejects_missing_scan_font_and_secret(monkeypatch):
    monkeypatch.setenv('FILE_SCAN_MODE', 'basic')
    monkeypatch.delenv('FILE_SCAN_COMMAND', raising=False)
    monkeypatch.delenv('PDF_DIGEST_FONT_PATH', raising=False)
    monkeypatch.delenv('JWT_SECRET_KEY', raising=False)
    errors = runtime_check.runtime_errors()
    assert len(errors) == 4
    assert any('external' in item for item in errors)


def test_production_preflight_requires_live_scanner_and_authorized_font(tmp_path, monkeypatch):
    font = tmp_path / 'font.ttf'
    font.write_bytes(b'font checked by exporter validation')
    monkeypatch.setenv('FILE_SCAN_MODE', 'external')
    monkeypatch.setenv('FILE_SCAN_COMMAND', 'pipesight-file-scan')
    monkeypatch.setenv('PDF_DIGEST_FONT_PATH', str(font))
    monkeypatch.setenv('JWT_SECRET_KEY', 'synthetic-test-key-only-for-offline-probe-20261120')
    monkeypatch.setattr(runtime_check.shutil, 'which', lambda _: '/bin/pipesight-file-scan')
    monkeypatch.setattr(runtime_check, 'validate_runtime_fonts', lambda **_kwargs: None)
    monkeypatch.setattr(runtime_check, 'scan_file', lambda *_a, **_kw: (0, 'PONG'))
    assert runtime_check.runtime_errors() == []
    monkeypatch.setattr(runtime_check, 'scan_file', lambda *_a, **_kw: (2, 'unavailable'))
    assert runtime_check.runtime_errors() == ['ClamAV 未就绪，请检查服务及病毒库']


def test_pdf_never_falls_back_to_unembedded_cid_font(monkeypatch):
    from app.research.services import exporters

    monkeypatch.setattr(exporters.pdfmetrics, 'getRegisteredFontNames', list)
    monkeypatch.setattr(Path, 'is_file', lambda _: False)
    with pytest.raises(ValueError, match='可嵌入'):
        exporters._pdf_font()


@pytest.mark.parametrize('key_kind', ['short', 'public_default'])
def test_production_preflight_rejects_development_signing_keys(monkeypatch, key_kind):
    from config.env import JwtSettings

    key = 'short' if key_kind == 'short' else JwtSettings.model_fields['jwt_secret_key'].default
    monkeypatch.setenv('JWT_SECRET_KEY', key)
    assert any('生产密钥不能使用开发默认值或短密钥' in error for error in runtime_check.runtime_errors())
