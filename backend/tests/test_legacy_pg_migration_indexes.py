"""Current schema files must also be usable while upgrading older PG tables."""

import ast
import importlib.util
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


@pytest.mark.parametrize('filename', [
    '20260814_pipeline_domain_enhancement.py',
    '20260814_full_system_redesign.py',
])
def test_old_postgresql_table_defers_future_column_indexes_and_can_reconcile_them(
    filename: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = Path(__file__).parents[1] / 'alembic' / 'versions' / filename
    spec = importlib.util.spec_from_file_location('legacy_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = tmp_path / 'schema.sql'
    schema.write_text(
        'CREATE INDEX IF NOT EXISTS idx_legacy_name ON legacy_files(name);\n'
        'CREATE INDEX IF NOT EXISTS idx_legacy_lease ON legacy_files(lease_until, name);\n'
        'CREATE INDEX IF NOT EXISTS idx_legacy_expression ON legacy_files(lower(name));\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(migration, '_schema_path', lambda _: schema)
    monkeypatch.setattr(migration.context, 'is_offline_mode', lambda: False)
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE legacy_files (name TEXT)')
        # SQLite shares IF NOT EXISTS index syntax, letting us execute the
        # actual DDL while exercising the PostgreSQL compatibility branch.
        monkeypatch.setattr(connection.dialect, 'name', 'postgresql')
        with Operations.context(MigrationContext.configure(connection)):
            migration._execute_schema_file('schema.sql')
            indexes = {item['name'] for item in inspect(connection).get_indexes('legacy_files')}
            assert 'idx_legacy_name' in indexes
            assert 'idx_legacy_lease' not in indexes
            assert connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_legacy_expression'"
            ).scalar_one() == 'idx_legacy_expression'
            connection.exec_driver_sql('ALTER TABLE legacy_files ADD COLUMN lease_until TEXT')
            migration._execute_schema_file('schema.sql')
            indexes = {item['name'] for item in inspect(connection).get_indexes('legacy_files')}
            assert 'idx_legacy_lease' in indexes


def test_alembic_url_round_trips_percent_encoded_password_characters() -> None:
    path = Path(__file__).parents[1] / 'alembic' / 'env.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    statement = next(
        node for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == 'set_main_option'
    )
    url = 'postgresql+asyncpg://test:sample%40with%25symbols@127.0.0.1/test'
    config = Config()
    # Exercise the actual environment configuration expression without importing
    # env.py, which would run migrations as a side effect.
    exec(compile(ast.Module(body=[statement], type_ignores=[]), str(path), 'exec'), {
        'alembic_config': config, 'ASYNC_SQLALCHEMY_DATABASE_URL': url,
    })
    assert config.get_main_option('sqlalchemy.url') == url
