"""Historical migration safety remains covered after processing retirement."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEGACY_VIEWS = (
    'sys_domain',
    'hp_data_source',
    'hp_domain',
    'hp_topic',
    'hp_news',
    'sys_prompt_version',
    'act_domain_topic_actions',
    'news_prompt_usage',
    'news_embedding',
)


def test_fresh_schema_does_not_recreate_legacy_views() -> None:
    schema = (ROOT / 'sql/insighthub-schema.pg.sql').read_text()
    for name in LEGACY_VIEWS:
        assert f'CREATE OR REPLACE VIEW news.{name}' not in schema
    assert 'news.sys_domain,' not in schema


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        'retire_views_migration', ROOT / 'alembic/versions/20261025_retire_processing_compat_views.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('problem', ['table', 'wrong_source', None])
def test_migration_checks_all_targets_before_dropping_and_uses_restrict(
    monkeypatch: pytest.MonkeyPatch, problem: str | None
) -> None:
    migration = load_migration()

    class Result:
        def __init__(self, value: Any) -> None:
            self.value = value

        def scalar_one_or_none(self) -> Any:
            return self.value

        def scalars(self) -> 'Result':
            return self

        def all(self) -> Any:
            return self.value

    class Bind:
        dialect = SimpleNamespace(name='postgresql')

        def __init__(self) -> None:
            self.writes = []

        def execute(self, statement: Any, params: dict[str, str]) -> Result:
            view = params['name'].split('.')[1]
            broken = view == 'news_embedding'
            if 'SELECT relkind' in str(statement):
                return Result('r' if problem == 'table' and broken else 'v')
            return Result(
                ['news.unrelated' if problem == 'wrong_source' and broken else f'news.{migration.VIEWS[view]}']
            )

        def exec_driver_sql(self, statement: str) -> None:
            self.writes.append(statement)

    bind = Bind()
    monkeypatch.setattr(migration.op, 'get_bind', lambda: bind)
    if problem:
        with pytest.raises(RuntimeError):
            migration.upgrade()
        assert not bind.writes
    else:
        migration.upgrade()
        drops = [s for s in bind.writes if s.startswith('DROP')]
        assert len(drops) == len(LEGACY_VIEWS)
        assert all(s.endswith(' RESTRICT') and 'CASCADE' not in s for s in drops)
        assert all('list_table' not in s and 'list_column' not in s for s in drops)
