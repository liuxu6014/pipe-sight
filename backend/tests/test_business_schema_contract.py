"""A complete business guard must not mistake names alone for schema parity."""

# Literal counts independently assert the approved table/field/FK inventory.
# ruff: noqa: PLR2004
from copy import deepcopy

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.business_schema import BUSINESS_TABLES, canonical_catalog, load_frozen, model_ddl, schema_differences
from app.infrastructure.models.registry import register_sqlalchemy_models
from config.database import Base


def specimen() -> dict:
    return {
        'reports': {
            'columns': [{'name': 'version', 'type': 'integer', 'nullable': False, 'default': '1', 'identity': ''}],
            'checks': [
                {
                    'name': 'ck_reports_type',
                    'definition': "CHECK (type = ANY (ARRAY['article'::text]))",
                    'validated': True,
                }
            ],
            'indexes': [
                {
                    'name': 'idx_reports_user_id',
                    'definition': 'CREATE INDEX idx_reports_user_id ON public.reports USING btree (user_id, updated_at DESC, id)',
                    'unique': False,
                    'valid': True,
                }
            ],
            'foreign_keys': [
                {'columns': ['user_id'], 'target': 'sys_user', 'target_columns': ['id'], 'ondelete': 'RESTRICT'}
            ],
            'primary_key': ['id'],
            'unique': [],
            'comment': '成果',
        }
    }


@pytest.mark.parametrize(
    'kind,key,value',
    [
        ('columns', 'type', 'text'),
        ('columns', 'nullable', True),
        ('columns', 'default', None),
        ('columns', 'identity', 'd'),
        ('checks', 'validated', False),
        ('checks', 'definition', "CHECK (type = ANY (ARRAY['research'::text]))"),
        (
            'indexes',
            'definition',
            'CREATE INDEX idx_reports_user_id ON public.reports USING btree (user_id, updated_at, id)',
        ),
        ('indexes', 'unique', True),
        ('indexes', 'valid', False),
        ('foreign_keys', 'ondelete', 'CASCADE'),
    ],
)
def test_actual_semantic_drift_is_never_hidden(kind: str, key: str, value: object) -> None:
    expected = specimen()
    actual = deepcopy(expected)
    actual['reports'][kind][0][key] = value
    assert schema_differences(actual, expected) == ['reports:' + kind]


def test_narrow_pg18_array_normalization_keeps_input_unchanged() -> None:
    expected = specimen()
    actual = deepcopy(expected)
    actual['reports']['checks'][0]['definition'] = "CHECK (type = ANY (ARRAY['article'::character varying]::text[]))"
    saved = deepcopy(actual)
    assert schema_differences(actual, expected) == []
    assert actual == saved
    assert canonical_catalog(expected) == canonical_catalog(canonical_catalog(expected))


def test_frozen_business_contract_matches_all_and_only_business_models() -> None:
    register_sqlalchemy_models()
    before = str(CreateTable(Base.metadata.tables['papers']).compile(dialect=postgresql.dialect()))
    frozen = load_frozen()
    assert len(BUSINESS_TABLES) == 15
    assert set(frozen['model_ddl']) == set(frozen['catalog']) == set(BUSINESS_TABLES)
    assert model_ddl(Base.metadata) == frozen['model_ddl']
    assert str(CreateTable(Base.metadata.tables['papers']).compile(dialect=postgresql.dialect())) == before
    assert sum(len(t['columns']) for t in frozen['catalog'].values()) == 196
    assert sum(len(t['foreign_keys']) for t in frozen['catalog'].values()) == 29
    assert not any(n.startswith('sys_') for n in frozen['model_ddl'])
