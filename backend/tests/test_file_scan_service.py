import shlex
import sys
from pathlib import Path

import pytest

from app.system.services.file_scan import FileScanService
from config.env import UploadConfig, UploadSettings


def test_scan_settings_read_environment_at_instantiation(monkeypatch, tmp_path):
    monkeypatch.setattr(UploadSettings, 'UPLOAD_PATH', str(tmp_path / 'uploads'))
    monkeypatch.setattr(UploadSettings, 'DOWNLOAD_PATH', str(tmp_path / 'downloads'))
    monkeypatch.setenv('FILE_SCAN_MODE', ' BASIC ')
    monkeypatch.setenv('FILE_SCAN_COMMAND', ' clamdscan --no-summary ')
    monkeypatch.setenv('FILE_SCAN_TIMEOUT_SECONDS', '45')
    settings = UploadSettings()
    assert settings.FILE_SCAN_MODE == 'basic'
    assert settings.FILE_SCAN_COMMAND == 'clamdscan --no-summary'
    assert settings.FILE_SCAN_TIMEOUT_SECONDS == 45
    monkeypatch.delenv('FILE_SCAN_MODE')
    monkeypatch.delenv('FILE_SCAN_COMMAND')
    monkeypatch.setenv('FILE_SCAN_TIMEOUT_SECONDS', 'invalid')
    settings = UploadSettings()
    assert settings.FILE_SCAN_MODE == 'external'
    assert settings.FILE_SCAN_COMMAND == ''
    assert settings.FILE_SCAN_TIMEOUT_SECONDS == 30


def test_scan_without_external_engine_stays_pending(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / '资料.txt'
    source.write_text('管道资料', encoding='utf-8')
    monkeypatch.setattr(UploadConfig, 'FILE_SCAN_COMMAND', '')
    monkeypatch.setattr(UploadConfig, 'FILE_SCAN_MODE', 'external')

    result = FileScanService.scan(str(source), source.name)

    assert result.status == 'pending'
    assert result.scanner_name == 'unconfigured'


def test_scan_command_exit_zero_marks_file_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / '资料.txt'
    source.write_text('管道资料', encoding='utf-8')
    command = f'{shlex.quote(sys.executable)} -c "import sys; sys.exit(0)"'
    monkeypatch.setattr(UploadConfig, 'FILE_SCAN_COMMAND', command)
    monkeypatch.setattr(UploadConfig, 'FILE_SCAN_MODE', 'external')

    result = FileScanService.scan(str(source), source.name)

    assert result.status == 'clean'
    assert result.scanner_name == sys.executable
    assert result.scanned_at is not None


def test_scan_command_exit_one_quarantines_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / '资料.txt'
    source.write_text('管道资料', encoding='utf-8')
    command = f'{shlex.quote(sys.executable)} -c "import sys; sys.exit(1)"'
    monkeypatch.setattr(UploadConfig, 'FILE_SCAN_COMMAND', command)
    monkeypatch.setattr(UploadConfig, 'FILE_SCAN_MODE', 'external')

    result = FileScanService.scan(str(source), source.name)

    assert result.status == 'quarantined'
    assert '风险' in result.message


def test_basic_scan_marks_document_clean_with_explicit_capability_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / '资料.md'
    source.write_text('# 管道资料', encoding='utf-8')
    monkeypatch.setattr(UploadConfig, 'FILE_SCAN_MODE', 'basic')

    result = FileScanService.scan(str(source), source.name)

    assert result.status == 'clean'
    assert result.scanner_name == 'builtin-basic'
    assert '病毒库' in result.message


def test_basic_scan_quarantines_common_executable_signature(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / '伪装资料.txt'
    source.write_bytes(b'MZ' + b'\x00' * 20)
    monkeypatch.setattr(UploadConfig, 'FILE_SCAN_MODE', 'basic')

    result = FileScanService.scan(str(source), source.name)

    assert result.status == 'quarantined'
    assert result.signature == 'executable-signature'
