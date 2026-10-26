"""Opt-in nonempty local PG18/asyncpg/Alembic rehearsal; no production access."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.environ.get('PIPESIGHT_SEEDED_NUMERIC_REHEARSE') != '1',
                    reason='Explicit unique labelled-local-database seeded rehearsal only')
def test_nonempty_numeric_ids_real_asyncpg_alembic_and_rollback() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / '.runtime/numeric-ids-CrDrud/seeded_rehearsal.py'
    result = subprocess.run([sys.executable, str(script)], cwd=root / 'backend',
                            capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, result.stderr[-6000:]
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report['actual_savepoint_failure_rollback'] == 'passed'
    assert report['actual_outer_transaction_rollback'] == 'passed'
    assert report['json_and_system_keys'] == 'passed'
    assert report['actual_queue_existing_scalar_string_replay'] == 'passed'
    assert report['actual_queue_changed_type_rejected'] == 'passed'
    assert report['actual_queue_changed_selection_rejected'] == 'passed'
    assert report['actual_queue_readonly_rollback'] == 'passed'
    assert report['no_live_database_connected'] is True
    assert report['seeded_tables'] and report['mapped_records'] > 0
    assert Path(report['evidence']).is_file()
