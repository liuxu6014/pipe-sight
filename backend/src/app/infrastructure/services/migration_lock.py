"""Serialize online migrations for one PostgreSQL database across processes."""

from collections.abc import Iterator
from contextlib import contextmanager

from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection

# PostgreSQL advisory locks are database-scoped and session-owned. Keep the key
# stable across releases, including direct Alembic and the safe migration CLI.
MIGRATION_LOCK_KEY = 0x5069706553696768


@contextmanager
def migration_lock(connection: Connection, *, expected_revision: str | None = None) -> Iterator[None]:
    if connection.dialect.name != 'postgresql':
        yield
        return
    acquired = connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': MIGRATION_LOCK_KEY})
    connection.commit()
    if not acquired:
        raise RuntimeError('另一个发布进程正在迁移此数据库，请等待其完成后重新检查并执行迁移。')
    try:
        if expected_revision is not None:
            heads = MigrationContext.configure(connection).get_current_heads()
            connection.rollback()
            if heads != (expected_revision,):
                raise RuntimeError('数据库版本在迁移规划后已改变，请重新核对版本与备份后再执行；本次未执行迁移。')
        yield
    finally:
        # Never commit an interrupted migration while releasing its lock.
        if connection.in_transaction():
            connection.rollback()
        connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': MIGRATION_LOCK_KEY})
        connection.commit()
