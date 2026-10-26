import sys
from urllib.parse import quote_plus

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.env import DataBaseConfig


def build_async_sqlalchemy_database_url() -> str:
    """
    构建异步 SQLAlchemy 数据库连接 URL

    :return: 异步 SQLAlchemy 数据库连接 URL
    """
    if DataBaseConfig.db_type == 'postgresql':
        return (
            f'postgresql+asyncpg://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
            f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
        )
    return (
        f'mysql+asyncmy://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )


ASYNC_SQLALCHEMY_DATABASE_URL = build_async_sqlalchemy_database_url()


def build_sync_sqlalchemy_database_url() -> str:
    """
    构建同步 SQLAlchemy 数据库连接 URL

    :return: 同步 SQLAlchemy 数据库连接 URL
    """
    if DataBaseConfig.db_type == 'postgresql':
        return (
            f'postgresql+psycopg2://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
            f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
        )
    return (
        f'mysql+pymysql://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )


SYNC_SQLALCHEMY_DATABASE_URL = build_sync_sqlalchemy_database_url()


def create_async_db_engine(echo: bool | None = None) -> AsyncEngine:
    """
    创建异步 SQLAlchemy Engine

    :param echo: 可选，是否输出 SQLAlchemy SQL 日志
    :return: 异步 SQLAlchemy Engine
    """
    return create_async_engine(
        ASYNC_SQLALCHEMY_DATABASE_URL,
        echo=DataBaseConfig.db_echo if echo is None else echo,
        max_overflow=DataBaseConfig.db_max_overflow,
        pool_size=DataBaseConfig.db_pool_size,
        pool_recycle=DataBaseConfig.db_pool_recycle,
        pool_timeout=DataBaseConfig.db_pool_timeout,
    )


def create_sync_db_engine(echo: bool | None = None) -> Engine:
    """
    创建同步 SQLAlchemy Engine

    :param echo: 可选，是否输出 SQLAlchemy SQL 日志
    :return: 同步 SQLAlchemy Engine
    """
    return create_engine(
        SYNC_SQLALCHEMY_DATABASE_URL,
        echo=DataBaseConfig.db_echo if echo is None else echo,
        max_overflow=DataBaseConfig.db_max_overflow,
        pool_size=DataBaseConfig.db_pool_size,
        pool_recycle=DataBaseConfig.db_pool_recycle,
        pool_timeout=DataBaseConfig.db_pool_timeout,
    )


def create_async_session_local(engine: AsyncEngine) -> async_sessionmaker:
    """
    创建异步 Session 工厂

    :param engine: 异步 SQLAlchemy Engine
    :return: 异步 Session 工厂
    """
    # AsyncSession 不能在普通属性访问中隐式执行过期字段的同步懒加载。
    # 提交后保留已加载状态，避免 Worker 在 commit 后读取 ORM 字段时触发
    # MissingGreenlet；需要最新数据的流程应显式 refresh/re-query。
    return async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def create_sync_session_local(engine: Engine) -> sessionmaker:
    """
    创建同步 Session 工厂

    :param engine: 同步 SQLAlchemy Engine
    :return: 同步 Session 工厂
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


_is_alembic_offline = 'alembic' in sys.argv[0].lower() and '--sql' in sys.argv
async_engine = None if _is_alembic_offline else create_async_db_engine()
AsyncSessionLocal = None if async_engine is None else create_async_session_local(async_engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass
