"""Connection manifest for disposable PG18 tests; never reads application settings."""

import json
import os
import re
from pathlib import Path


def rehearsal_manifest() -> dict:
    path = Path(os.environ['PIPESIGHT_PG_REHEARSAL_MANIFEST'])
    manifest = json.loads(path.read_text())
    info = manifest['connection']
    assert (info['host'], info['port'], info['dbname']) == ('127.0.0.1', 19432, 'pipesight_rehearsal')
    for key in ('legacy_database', 'current_database'):
        assert re.fullmatch(r'pipesight_(?:compact|beijing)_pgtest_[a-f0-9]{12}', manifest[key])
    return manifest


def connection_info(kind: str = 'current') -> dict:
    manifest = rehearsal_manifest()
    return {**manifest['connection'], 'dbname': manifest[f'{kind}_database']}


def snapshot_root() -> Path:
    return Path(rehearsal_manifest()['snapshot_root'])
