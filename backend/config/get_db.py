from collections.abc import AsyncGenerator

from sqlalchemy import BigInteger, Integer, inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.services.logging_support import logger
from config.database import AsyncSessionLocal, Base, async_engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    每一个请求处理完毕后会关闭当前连接，不同的请求使用不同的连接

    :return:
    """
    async with AsyncSessionLocal() as current_db:
        yield current_db


async def init_create_table() -> None:
    """
    应用启动时初始化数据库连接

    :return:
    """
    logger.info('🔎 初始化数据库连接...')
    async with async_engine.connect() as conn:
        await conn.run_sync(validate_schema)
    logger.info('✅️ 数据库连接成功')


def validate_schema(connection) -> None:
    """Migrations own DDL; a mismatched restart must never recreate old/new tables."""
    inspector = inspect(connection)
    mismatches = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name, schema=table.schema):
            mismatches.append(table.name)
            continue
        columns = {column['name']: column for column in inspector.get_columns(table.name, schema=table.schema)}
        if set(columns) != set(table.columns.keys()):
            mismatches.append(table.name)
            continue
        # Numeric-ID rollout changes types without changing field names. Never
        # accept the pre-migration VARCHAR schema simply because names match.
        from app.business_ids import BUSINESS_ID_TABLES

        for column in table.columns:
            numeric_id = (table.name in BUSINESS_ID_TABLES and column.name == 'id') or any(
                fk.target_fullname.split('.')[-2] in BUSINESS_ID_TABLES for fk in column.foreign_keys
            )
            if numeric_id:
                expected = Integer if connection.dialect.name == 'sqlite' else BigInteger
                if not isinstance(columns[column.name].get('type'), expected):
                    mismatches.append(table.name + '.' + column.name)
    if mismatches:
        raise RuntimeError('数据库结构与当前代码不一致，请先完成备份和迁移：' + ', '.join(mismatches))
    from app.business_schema import validate_business_schema

    validate_business_schema(connection, Base.metadata)


async def close_async_engine() -> None:
    """
    应用关闭时释放数据库连接池

    :return:
    """
    await async_engine.dispose()
