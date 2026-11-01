"""Drive the five backup-gated PipeSight migrations programmatically on a scratch DB.

Runs compact -> restore_ruoyi_names -> numeric_business_ids -> business_consistency
-> beijing_audit_time, generating the verified backup manifests between phases and
stamping ``alembic_version`` progressively (business_consistency and beijing_audit_time
re-read the live revision during execution). This is a rehearsal against the
``pipesight`` scratch database on the server; the helpers are POSIX-only, so it must
run inside the Linux container. The digest migration and ``validate_schema`` run
afterwards via ``alembic upgrade head`` + ``_verify_schema.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import sqlalchemy as sa

ARTIFACTS = Path('/artifacts')
TZ = 'Asia/Shanghai'


def fingerprint_table(bind: sa.Connection, qualified_name: str) -> list:
    """The [count, md5] PG-row-JSON recipe every migration re-derives under lock."""
    from app.schema_migration import _qualified

    row = bind.execute(
        sa.text(
            "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
            f'(SELECT md5(row_to_json(t)::text) h FROM {_qualified(qualified_name)} t) s'
        )
    ).one()
    return list(row)


def stamp(bind: sa.Connection, version: str) -> None:
    bind.execute(sa.text('DELETE FROM public.alembic_version'))
    bind.execute(sa.text('INSERT INTO public.alembic_version (version_num) VALUES (:v)'), {'v': version})


def write_dump_and_manifest(root: Path, revision: str, tables: list[str], bind: sa.Connection) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    fingerprints = {name: fingerprint_table(bind, 'public.' + name) for name in sorted(tables)}
    dump = json.dumps(
        {'revision': revision, 'tables': sorted(tables), 'fingerprints': fingerprints}, sort_keys=True
    ).encode()
    (root / 'database-before.dump').write_bytes(dump)
    manifest = {
        'revision': revision,
        'tables': sorted(tables),
        'fingerprints': fingerprints,
        'sha256': hashlib.sha256(dump).hexdigest(),
    }
    (root / 'database-before.json').write_text(json.dumps(manifest, sort_keys=True))
    return manifest


def main() -> None:
    from config.database import create_sync_db_engine
    from app.schema_migration import SOURCE_TABLES, archive_plan, migrate, preflight
    from app.ruoyi_table_names import RUOYI_TABLE_NAMES, restore_ruoyi_names
    from app.numeric_id_migration import migrate_numeric_ids
    from app.business_schema_migration import migrate_business_consistency
    from app.beijing_time_migration import migrate_beijing_audit_time

    engine = create_sync_db_engine(echo=False)

    # Clear leftover phase artifacts from any prior partial run. The migration
    # helpers chmod backup dirs 0700 and create archives with O_EXCL, so a stale
    # dir/file would make a re-run abort; these dirs are root-owned, so only the
    # container (root) can remove them.
    for name in ('numeric', 'restore', 'business', 'beijing'):
        path = ARTIFACTS / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    for name in ('compact-archive.json', 'compact-source-snapshot.json'):
        path = ARTIFACTS / name
        if path.exists():
            path.unlink()

    # ---- Phase 1: compact --------------------------------------------------
    print('== Phase 1: compact ==', flush=True)
    with engine.connect() as bind:
        plan = preflight(bind, historical_timezone=TZ, allow_live=True)
    archive_path = ARTIFACTS / 'compact-archive.json'
    if archive_path.exists():
        archive_path.unlink()
    sha = archive_plan(plan, archive_path)
    print('compact archive sha256:', sha, flush=True)

    snapshot = {'fingerprints': {}}
    with engine.connect() as bind:
        for name in sorted(SOURCE_TABLES):
            snapshot['fingerprints'][name] = fingerprint_table(bind, name)
    (ARTIFACTS / 'compact-source-snapshot.json').write_text(json.dumps(snapshot, sort_keys=True))

    with engine.begin() as bind:
        report = migrate(
            bind,
            archive_path=str(archive_path),
            archive_sha256=sha,
            historical_timezone=TZ,
            expected_source_fingerprints=plan.source_fingerprints,
            source_snapshot=snapshot,
            optional_tables=plan.optional_tables,
            allow_live=True,
        )
    print('compact OK:', json.dumps(report, ensure_ascii=False, default=str)[:400], flush=True)

    # ---- Phase 2: restore RuoYi names --------------------------------------
    print('== Phase 2: restore RuoYi names ==', flush=True)
    from app.schema_comments_v2 import TABLE_COMMENTS as T2

    source2 = (set(T2) - set(RUOYI_TABLE_NAMES.values())) | set(RUOYI_TABLE_NAMES)
    with engine.connect() as bind:
        manifest2 = write_dump_and_manifest(ARTIFACTS / 'restore', '20261025_compact_schema', sorted(source2), bind)
    with engine.begin() as bind:
        report2 = restore_ruoyi_names(bind, manifest=manifest2, allow_live=True)
    print('restore OK:', json.dumps(report2, ensure_ascii=False, default=str)[:400], flush=True)

    # ---- Phase 3: numeric business IDs -------------------------------------
    print('== Phase 3: numeric IDs ==', flush=True)
    from app.schema_comments import TABLE_COMMENTS as T0

    tables0 = sorted(T0)
    with engine.connect() as bind:
        manifest3 = write_dump_and_manifest(ARTIFACTS / 'numeric', '20261025_restore_ruoyi_names', tables0, bind)
    with engine.begin() as bind:
        report3 = migrate_numeric_ids(bind, manifest=manifest3, backup_dir=ARTIFACTS / 'numeric', allow_live=True)
    print('numeric OK:', json.dumps(report3, ensure_ascii=False, default=str)[:400], flush=True)

    # business_consistency checks the live revision during execution.
    with engine.begin() as bind:
        stamp(bind, '20261025_numeric_business_ids')

    # ---- Phase 4: business consistency -------------------------------------
    print('== Phase 4: business consistency ==', flush=True)
    with engine.connect() as bind:
        tables4 = sorted(sa.inspect(bind).get_table_names(schema='public'))
        manifest4 = write_dump_and_manifest(ARTIFACTS / 'business', '20261025_numeric_business_ids', tables4, bind)
    with engine.begin() as bind:
        report4 = migrate_business_consistency(bind, backup_dir=ARTIFACTS / 'business', allow_live=True)
    print('business consistency OK:', json.dumps(report4, ensure_ascii=False, default=str)[:400], flush=True)

    with engine.begin() as bind:
        stamp(bind, '20261025_business_consistency')

    # ---- Phase 5: Beijing audit time ---------------------------------------
    print('== Phase 5: Beijing audit time ==', flush=True)
    with engine.connect() as bind:
        tables5 = sorted(sa.inspect(bind).get_table_names(schema='public'))
        manifest5 = write_dump_and_manifest(ARTIFACTS / 'beijing', '20261025_business_consistency', tables5, bind)
    with engine.begin() as bind:
        report5 = migrate_beijing_audit_time(bind, backup_dir=ARTIFACTS / 'beijing', allow_live=True)
    print('beijing OK:', json.dumps(report5, ensure_ascii=False, default=str)[:400], flush=True)

    with engine.begin() as bind:
        stamp(bind, '20261025_beijing_audit_time')

    print('ALL FIVE GATED PHASES DONE (digest + validate_schema run next)', flush=True)


if __name__ == '__main__':
    main()
