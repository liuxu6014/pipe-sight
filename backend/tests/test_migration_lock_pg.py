"""Two actual processes contend on the labelled local rehearsal database only."""

import json
import os
import subprocess
import sys

import pytest
from pg_rehearsal import connection_info

CHILD = """
import json, sys
from sqlalchemy import URL, create_engine, text
from app.infrastructure.services.migration_lock import migration_lock
data = json.loads(sys.stdin.readline())
info, mode = data['connection'], data['mode']
engine = create_engine(URL.create('postgresql+psycopg2', username=info['user'],
    password=info['password'], host=info['host'], port=info['port'], database=info['dbname']),
    connect_args={'connect_timeout': 5}, hide_parameters=True)
try:
    with engine.connect() as connection:
        expected = 'deliberately_stale_revision' if mode == 'stale' else None
        with migration_lock(connection, expected_revision=expected):
            print('LOCKED', flush=True)
            if mode == 'hold':
                sys.stdin.readline()
            if mode == 'error':
                raise ValueError('synthetic interrupted migration')
except RuntimeError as exc:
    print(str(exc), flush=True)
    sys.exit(42)
except ValueError:
    sys.exit(43)
finally:
    engine.dispose()
"""


def test_two_migration_processes_cannot_enter_together_and_release_after_failure():
    if os.environ.get('PIPESIGHT_REPORT_METADATA_PG') != '1':
        pytest.skip('Explicit isolated local PostgreSQL rehearsal opt-in required')
    info = connection_info()
    assert (info['host'], int(info['port'])) == ('127.0.0.1', 19432)

    def run(mode):
        return subprocess.run(
            [sys.executable, '-c', CHILD],
            input=json.dumps({'connection': info, 'mode': mode}) + '\n',
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )

    holder = subprocess.Popen(
        [sys.executable, '-c', CHILD], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        holder.stdin.write(json.dumps({'connection': info, 'mode': 'hold'}) + '\n')
        holder.stdin.flush()
        # Child only reads labelled loopback connection data and does not write schema/data.
        import select

        ready, _, _ = select.select([holder.stdout], [], [], 15)
        assert ready and holder.stdout.readline().strip() == 'LOCKED'
        contender = run('try')
        assert contender.returncode == 42 and '另一个发布进程' in contender.stdout
        holder.stdin.write('\n')
        holder.stdin.flush()
        holder.communicate(timeout=15)
        assert holder.returncode == 0
        assert run('try').returncode == 0
        failed = run('error')
        assert failed.returncode == 43
        assert run('try').returncode == 0
        stale = run('stale')
        assert stale.returncode == 42 and '版本在迁移规划后已改变' in stale.stdout
        assert run('try').returncode == 0
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.communicate(timeout=5)
