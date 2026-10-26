"""Short names must remain semantic, collision-free, and resolvable by the ORM."""

# Literal counts assert the approved baseline and its four optional foreign keys.
# ruff: noqa: PLR2004

import importlib.util
import re
from pathlib import Path

from sqlalchemy.dialects import postgresql

from app.business_ids import BUSINESS_ID_SEQUENCE, BUSINESS_ID_TABLES
from app.infrastructure.models.registry import register_sqlalchemy_models
from app.schema_comments import COLUMN_COMMENTS, FRAMEWORK_TABLE_NAMES, OPTIONAL_TABLE_NAMES
from app.schema_contract import FOUNDATION_TABLE_RENAMES, load_contract
from config.database import Base
from config.schema_documentation import APPLICATION_INTERMEDIATE_RENAMES, APPLICATION_TABLE_RENAMES

RENAMED_TABLE_COUNT = 11


def test_short_names_and_foreign_keys_are_complete() -> None:
    register_sqlalchemy_models()
    contract = load_contract()
    baseline = {table['name']: table for table in contract['tables']}
    expected = (set(baseline) | set(OPTIONAL_TABLE_NAMES)) - set(FRAMEWORK_TABLE_NAMES)
    assert set(Base.metadata.tables) == expected
    assert len(baseline) == 27 and len(expected) == 27
    for table in Base.metadata.tables.values():
        if table.name not in FOUNDATION_TABLE_RENAMES.values():
            assert re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)?', table.name), table.name
        assert set(table.c.keys()) == set(COLUMN_COMMENTS[table.name])
        if table.name in baseline:
            fields = baseline[table.name]['columns']
            assert set(table.c.keys()) == {column['name'] for column in fields}
            assert [column.name for column in table.primary_key] == [column['name'] for column in fields if column['primary_key']]
        for column in table.c:
            for foreign_key in column.foreign_keys:
                assert foreign_key.column is not None
    actual_fks = {(table.name, tuple(fk.column_keys), fk.referred_table.name,
                   tuple(element.column.name for element in fk.elements))
                  for table in Base.metadata.tables.values() for fk in table.foreign_key_constraints}
    baseline_fks = {(fk['table'], tuple(fk['columns']), fk['target'], tuple(fk['target_columns']))
                    for fk in contract['foreign_keys']}
    assert baseline_fks <= actual_fks
    assert len(actual_fks - baseline_fks) == 4


def test_migration_frozen_map_matches_runtime_contract() -> None:
    # Historical mapping belongs to its migration stage, not today's inventory.
    assert len(APPLICATION_TABLE_RENAMES) == len(set(APPLICATION_TABLE_RENAMES.values())) == RENAMED_TABLE_COUNT
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/20261014_short_business_table_names.py'
    spec = importlib.util.spec_from_file_location('short_names_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert {old: APPLICATION_INTERMEDIATE_RENAMES.get(new, new) for old, new in module.RENAMES.items()} == APPLICATION_TABLE_RENAMES
    assert module.short_name('idx_pipeline_quality_issue_status_time') == 'idx_quality_issue_status_time'
    assert module.short_name('pipeline_model_route_usage_pkey') == 'route_usage_pkey'
    assert module.identifier('a"b') == '"a""b"'


def test_runtime_numeric_models_match_current_bigint_pk_fk_and_shared_sequence() -> None:
    register_sqlalchemy_models()
    contract = load_contract()
    dialect = postgresql.dialect()
    assert set(contract['business_id_policy']['tables']) == set(BUSINESS_ID_TABLES)
    for name in BUSINESS_ID_TABLES:
        column = Base.metadata.tables[name].c.id
        assert str(column.type.compile(dialect=dialect)) == 'BIGINT'
        assert column.default is BUSINESS_ID_SEQUENCE
        assert 'business_id_seq' in str(column.server_default.arg.compile(dialect=dialect))
    for fk in contract['foreign_keys'] + contract['optional_foreign_keys']:
        for column_name, target_column in zip(fk['columns'], fk['target_columns'], strict=True):
            column = Base.metadata.tables[fk['table']].c[column_name]
            target = Base.metadata.tables[fk['target']].c[target_column]
            assert str(column.type.compile(dialect=dialect)) == str(target.type.compile(dialect=dialect))
            if fk['target'] in BUSINESS_ID_TABLES:
                assert str(column.type.compile(dialect=dialect)) == 'BIGINT'
    for name in ('ai_models', 'basket_items', 'report_versions'):
        assert Base.metadata.tables[name].c.id.default is not BUSINESS_ID_SEQUENCE
    for name in ('generation_tasks', 'collection_runs'):
        assert str(Base.metadata.tables[name].c.execution_token.type.compile(dialect=dialect)) == 'VARCHAR(64)'
        assert str(Base.metadata.tables[name].c.request_id.type.compile(dialect=dialect)) == 'VARCHAR(128)'


def test_semantic_migration_does_not_double_prefix_existing_index_names() -> None:
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/20261014_semantic_business_names.py'
    spec = importlib.util.spec_from_file_location('semantic_names_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.RENAMES == APPLICATION_INTERMEDIATE_RENAMES
    assert module.short_name('route_usage_pkey') == 'model_route_usage_pkey'
    assert module.short_name('idx_model_route_usage_date') == 'idx_model_route_usage_date'
    register_sqlalchemy_models()
    assert not set(APPLICATION_INTERMEDIATE_RENAMES).intersection(Base.metadata.tables)
