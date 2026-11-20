"""Forward migration entry point with explicit historical backup gates.

This command never creates a database, stamps a revision, restores a dump or
removes historical safeguards. A legacy rollout advances one backed-up stage
at a time; the next stage needs a fresh snapshot of the new source revision.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    from alembic.script import ScriptDirectory
    from sqlalchemy import Connection


class MigrationSafetyError(RuntimeError):
    """A deployment prerequisite needs an explicit operator action."""


HISTORICAL_GATES = {
    '20261025_compact_schema': (
        'compact_archive',
        'compact_archive_sha256',
        'compact_source_snapshot',
        'historical_timezone',
    ),
    '20261025_restore_ruoyi_names': ('ruoyi_backup',),
    '20261025_numeric_business_ids': ('numeric_backup',),
    '20261025_business_consistency': ('business_backup',),
    '20261025_beijing_audit_time': ('beijing_backup',),
}
ALLOW_LIVE = {
    '20261025_compact_schema': 'compact_allow_live',
    '20261025_restore_ruoyi_names': 'ruoyi_allow_live',
    '20261025_numeric_business_ids': 'numeric_allow_live',
    '20261025_business_consistency': 'business_allow_live',
    '20261025_beijing_audit_time': 'beijing_allow_live',
}
MAX_TCP_PORT = 65535


def backend_root() -> Path:
    # The image retains Alembic assets at /app. Local entry points also run
    # from the backend directory; an explicit path supports packaged installs.
    return Path(os.getenv('PIPESIGHT_MIGRATION_ROOT', '.')).resolve()


def inspect_revision(connection: Connection) -> str:
    """Read only: reject unversioned/empty databases instead of bootstrapping."""
    from sqlalchemy import inspect, text  # noqa: PLC0415

    if not inspect(connection).has_table('alembic_version'):
        raise MigrationSafetyError(
            '数据库尚未版本化；空库或历史无版本库必须先完成独立的受控初始化/迁移演练，本入口不会自动建库或 stamp。'
        )
    rows = list(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())
    if len(rows) != 1 or not isinstance(rows[0], str) or not rows[0]:
        raise MigrationSafetyError('数据库迁移版本为空或存在多个分支，请先核对迁移记录。')
    return rows[0]


async def current_revision() -> str:
    """Inspect exactly the explicitly configured PostgreSQL database."""
    from sqlalchemy import URL, text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    required = ('DB_HOST', 'DB_PORT', 'DB_DATABASE', 'DB_USERNAME', 'DB_PASSWORD')
    if os.getenv('DB_TYPE', 'postgresql') != 'postgresql' or any(not os.getenv(key) for key in required):
        raise MigrationSafetyError(
            '安全迁移要求显式提供 PostgreSQL 的 DB_HOST/PORT/DATABASE/USERNAME/PASSWORD，不读取 .env。'
        )
    try:
        port = int(os.environ['DB_PORT'])
        if not 1 <= port <= MAX_TCP_PORT:
            raise ValueError
    except ValueError as exc:
        raise MigrationSafetyError('DB_PORT 无效。') from exc
    url = URL.create(
        'postgresql+asyncpg',
        username=os.environ['DB_USERNAME'],
        password=os.environ['DB_PASSWORD'],
        host=os.environ['DB_HOST'],
        port=port,
        database=os.environ['DB_DATABASE'],
    )
    engine = create_async_engine(url, echo=False, connect_args={'timeout': 10})
    try:
        async with engine.connect() as connection:
            await connection.execute(text('SET TRANSACTION READ ONLY'))
            return await connection.run_sync(inspect_revision)
    except MigrationSafetyError:
        raise
    except Exception as exc:
        raise MigrationSafetyError('无法读取目标数据库迁移版本，请检查 DB_* 配置、网络及只读查询权限。') from exc
    finally:
        await engine.dispose()


def private_path(path: Path, *, directory: bool = False) -> Path:
    path = path.resolve()
    if not (path.is_dir() if directory else path.is_file()) or path.stat().st_mode & 0o077:
        raise MigrationSafetyError('历史迁移材料必须存在并为私有权限（目录0700、文件0600）。')
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verified_backup(folder: Path, source: str) -> dict:
    """Use the rehearsal dump + manifest + row-fingerprint contract."""
    root = private_path(folder, directory=True)
    manifest_path = private_path(root / 'database-before.json')
    dump = private_path(root / 'database-before.dump')
    try:
        manifest = json.loads(manifest_path.read_text())
    except (ValueError, OSError) as exc:
        raise MigrationSafetyError('备份清单无法读取。') from exc
    if not isinstance(manifest, dict) or manifest.get('revision') != source:
        raise MigrationSafetyError('备份修订与当前数据库不一致；每个历史转换前都需要该阶段的新快照。')
    digest = manifest.get('sha256', '')
    tables, fingerprints = manifest.get('tables'), manifest.get('fingerprints')
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or sha256_file(dump) != digest:
        raise MigrationSafetyError('备份 dump 的 SHA-256 与清单不一致。')
    if (
        not isinstance(tables, list)
        or not tables
        or not all(isinstance(table, str) for table in tables)
        or not isinstance(fingerprints, dict)
        or set(tables) != set(fingerprints)
    ):
        raise MigrationSafetyError('备份清单缺少完整表清单或行指纹。')
    return manifest


def load_options(path: Path, *, source: str, target: str) -> dict[str, str]:
    try:
        plan = json.loads(private_path(path).read_text())
    except (ValueError, OSError) as exc:
        raise MigrationSafetyError('迁移选项文件无法读取。') from exc
    if not isinstance(plan, dict) or plan.get('source_revision') != source or plan.get('target_revision') != target:
        raise MigrationSafetyError('迁移选项必须明确匹配当前修订和本次目标修订。')
    values = plan.get('x_arguments')
    required = HISTORICAL_GATES[target]
    allowed = {*required, ALLOW_LIVE[target]}
    if (
        not isinstance(values, dict)
        or set(values) - allowed
        or not all(isinstance(value, str) and value for value in values.values())
        or not all(values.get(key) for key in required)
    ):
        raise MigrationSafetyError('历史迁移参数缺失或包含不允许的 -x 选项。')
    if ALLOW_LIVE[target] in values and values[ALLOW_LIVE[target]] != 'true':
        raise MigrationSafetyError('allow_live 只能由操作人显式设为 true，不能自动授权。')
    if target == '20261025_compact_schema':
        snapshot = private_path(Path(values['compact_source_snapshot']))
        if snapshot.name != 'database-before.json':
            raise MigrationSafetyError('compact_source_snapshot 必须指向已验证备份目录中的 database-before.json。')
        verified_backup(snapshot.parent, source)
        archive = private_path(Path(values['compact_archive']))
        if sha256_file(archive) != values['compact_archive_sha256']:
            raise MigrationSafetyError('退役归档 SHA-256 不一致。')
        try:
            ZoneInfo(values['historical_timezone'])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise MigrationSafetyError('historical_timezone 必须是明确的有效时区。') from exc
    else:
        verified_backup(Path(values[required[0]]), source)
    return values


def migration_command(
    script: ScriptDirectory, *, source: str, target: str, options_file: Path | None, root: Path
) -> tuple[list[str] | None, str]:
    """Plan without touching DB; protected stages require one fresh backup each."""
    try:
        heads = script.get_heads()
        if len(heads) != 1:
            raise MigrationSafetyError('仓库存在多个迁移头，请先人工合并迁移分支。')
        destination = heads[0] if target == 'head' else script.get_revision(target).revision
        script.get_revision(source)
        pending = list(reversed(list(script.iterate_revisions(destination, source))))
    except MigrationSafetyError:
        raise
    except Exception as exc:
        raise MigrationSafetyError('目标不是当前数据库的已知前向迁移路径；拒绝降级或跳过历史转换。') from exc
    if not pending:
        return None, destination
    protected = [revision for revision in pending if revision.revision in HISTORICAL_GATES]
    options = {}
    if protected:
        gate = protected[0]
        if (
            target == 'head'
            or len(pending) != 1
            or gate.revision != destination
            or gate.down_revision != source
            or options_file is None
        ):
            raise MigrationSafetyError(
                f'历史升级需分阶段备份与复验。下一受保护阶段为 {gate.revision}；请按 docs/deployment-migrations.md 准备私有备份，显式指定 --target 和 --options-file。'
            )
        options = load_options(options_file, source=source, target=destination)
    else:
        try:
            # Earlier ordinary revisions may contain legacy destructive DDL;
            # only the controlled rollout owns that part of the chain.
            list(script.iterate_revisions(source, '20261025_beijing_audit_time'))
        except Exception as exc:
            raise MigrationSafetyError('较早历史版本必须先完成受控历史迁移方案，不能直接执行旧版转换。') from exc
        if options_file is not None:
            raise MigrationSafetyError('常规前向迁移不接受历史 -x 选项文件。')
    command = [sys.executable, '-m', 'alembic', '-c', str(root / 'alembic.ini')]
    for key, value in sorted(options.items()):
        command.extend(['-x', f'{key}={value}'])
    return [*command, 'upgrade', destination], destination


async def migrate(*, target: str, options_file: Path | None, root: Path) -> None:
    # Both the revision reader and Alembic must use explicit environment values.
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    from alembic.config import Config  # noqa: PLC0415
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    config = Config(str(root / 'alembic.ini'))
    script = ScriptDirectory.from_config(config)
    source = await current_revision()
    command, destination = migration_command(script, source=source, target=target, options_file=options_file, root=root)
    if command is None:
        print('数据库已处于目标迁移版本。')
        return
    environment = {
        **os.environ,
        'PYTHON_DOTENV_DISABLED': '1',
        'DB_ECHO': 'false',
        'PIPESIGHT_EXPECTED_SOURCE_REVISION': source,
    }
    result = await asyncio.to_thread(subprocess.run, command, cwd=root, env=environment, check=False)
    if result.returncode:
        raise MigrationSafetyError('Alembic 迁移未通过；API/Worker 不应启动。请核对迁移日志并保留备份。')
    if await current_revision() != destination:
        raise MigrationSafetyError('迁移后的版本核对不一致；拒绝启动应用。')
    print(f'迁移版本核对通过：{destination}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', default=os.getenv('PIPESIGHT_MIGRATION_TARGET', 'head'))
    parser.add_argument('--options-file', type=Path, default=os.getenv('PIPESIGHT_MIGRATION_OPTIONS_FILE') or None)
    args = parser.parse_args()
    try:
        asyncio.run(migrate(target=args.target, options_file=args.options_file, root=backend_root()))
    except MigrationSafetyError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
