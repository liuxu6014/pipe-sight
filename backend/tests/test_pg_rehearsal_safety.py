"""Reject live endpoints before the rehearsal tests can create a DB engine."""

import json

import pytest
from pg_rehearsal import connection_info


@pytest.mark.parametrize(
    'changed',
    [
        {'host': '172.16.4.183'},
        {'port': 25432},
        {'dbname': 'pipesight'},
        {'current_database': 'pipesight'},
        {'legacy_database': 'pipesight_rehearsal'},
    ],
)
def test_manifest_rejects_application_databases(tmp_path, monkeypatch, changed):
    manifest = {
        'connection': {'host': '127.0.0.1', 'port': 19432, 'dbname': 'pipesight_rehearsal'},
        'legacy_database': 'pipesight_compact_pgtest_123456abcdef',
        'current_database': 'pipesight_beijing_pgtest_123456abcdef',
    }
    for key, value in changed.items():
        if key in manifest:
            manifest[key] = value
        else:
            manifest['connection'][key] = value
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    monkeypatch.setenv('PIPESIGHT_PG_REHEARSAL_MANIFEST', str(path))
    with pytest.raises(AssertionError):
        connection_info()
