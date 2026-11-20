"""The v20 extension is explicit; published v19 snapshots and guards stay frozen."""

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from app.business_schema import load_frozen
from app.schema_comments import COLUMN_COMMENTS
from app.schema_contract import load_contract

ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_COLUMNS = {
    'category_id',
    'classification_status',
    'classification_error',
    'classification_token',
    'classification_updated_at',
}


def test_published_v19_files_remain_byte_identical():
    expected = {
        'compact-v19.json': '294a6f18a9c4093867c50b906eafdf25d413ef3bb4f60490a246dc4343a74cbe',
        'business-v19.json': '1cd5b4fe546810128203d8aeb3468c8071f3ad2182d28fc049ed78172d8118ff',
    }
    for filename, digest in expected.items():
        assert hashlib.sha256((ROOT / 'data/schema' / filename).read_bytes()).hexdigest() == digest


def test_compact_v20_adds_only_five_document_fields_and_one_category_relation():
    old, new = load_contract('v19'), load_contract('v20')
    before = {t['name']: t for t in old['tables']}
    after = {t['name']: t for t in new['tables']}
    assert before.keys() == after.keys()
    for name, table in before.items():
        if name == 'knowledge_files':
            assert table['columns'] == [c for c in after[name]['columns'] if c['name'] not in CLASSIFICATION_COLUMNS]
            added = {c['name']: c for c in after[name]['columns'] if c['name'] in CLASSIFICATION_COLUMNS}
            assert set(added) == CLASSIFICATION_COLUMNS
            assert added['classification_status']['server_default'] == "'not_configured'"
            assert not added['classification_status']['nullable']
            assert all(added[name]['nullable'] for name in CLASSIFICATION_COLUMNS - {'classification_status'})
            assert added['classification_updated_at']['type'] == 'timestamp(0) without time zone'
        else:
            assert table == after[name]
    assert new['foreign_keys'] == old['foreign_keys'] + [
        {'table': 'knowledge_files', 'columns': ['category_id'], 'target': 'categories', 'target_columns': ['id']}
    ]
    for key in (
        'optional_tables',
        'optional_table_definitions',
        'optional_foreign_keys',
        'business_id_policy',
        'sequences',
        'audit_timestamp_policy',
    ):
        assert old[key] == new[key]


def test_business_v20_preserves_other_tables_and_old_document_columns():
    old, new = load_frozen('v19'), load_frozen('v20')
    assert new['revision'] == '20261120_material_comments'
    for table in old['model_ddl']:
        if table not in {'knowledge_files', 'categories'}:
            assert old['model_ddl'][table] == new['model_ddl'][table]
            assert old['catalog'][table] == new['catalog'][table]
    for source in ('model_ddl', 'catalog'):
        original = {c['name']: c for c in old[source]['knowledge_files']['columns']}
        current = {c['name']: c for c in new[source]['knowledge_files']['columns']}
        assert set(current) - set(original) == CLASSIFICATION_COLUMNS
        for name, column in original.items():
            if name == 'updated_at':
                assert {k: v for k, v in column.items() if k != 'comment'} == {
                    k: v for k, v in current[name].items() if k != 'comment'
                }
                assert current[name]['comment'] == COLUMN_COMMENTS['knowledge_files']['updated_at']
            else:
                assert column == current[name]
        assert old[source]['knowledge_files']['foreign_keys'] == [
            fk for fk in new[source]['knowledge_files']['foreign_keys'] if fk['columns'] != ['category_id']
        ]
        assert old[source]['knowledge_files']['checks'] == [
            c
            for c in new[source]['knowledge_files']['checks']
            if c['name'] != 'ck_knowledge_files_classification_status'
        ]
        assert old[source]['knowledge_files']['indexes'] == [
            i
            for i in new[source]['knowledge_files']['indexes']
            if i['name'] != 'idx_knowledge_files_classification_queue'
        ]
    old_checks = old['model_ddl']['categories']['checks']
    new_checks = new['model_ddl']['categories']['checks']
    assert [c for c in old_checks if c['name'] != 'ck_categories_applies_to'] == [
        c for c in new_checks if c['name'] != 'ck_categories_applies_to'
    ]
    assert (
        next(c for c in new_checks if c['name'] == 'ck_categories_applies_to')['expression']
        == "applies_to IN ('news','paper','document','all')"
    )


def test_followup_migration_only_sets_declared_comments_and_new_timestamp_precision(monkeypatch):
    path = ROOT / 'alembic/versions/20261120_material_comments.py'
    spec = importlib.util.spec_from_file_location('material_comments_revision', path)
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    calls = []
    monkeypatch.setattr(
        revision,
        'op',
        SimpleNamespace(alter_column=lambda table, column, **kwargs: calls.append((table, column, kwargs))),
    )
    revision.upgrade()
    precision, *comments = calls
    assert precision[:2] == ('knowledge_files', 'classification_updated_at')
    assert precision[2]['type_'].precision == 0 and not precision[2]['type_'].timezone
    assert precision[2]['postgresql_using'] == "date_trunc('second', classification_updated_at)"
    assert set(revision.COMMENTS) == {
        ('categories', 'applies_to'),
        ('knowledge_files', 'updated_at'),
        *(('knowledge_files', name) for name in CLASSIFICATION_COLUMNS),
    }
    assert len(comments) == 7
    for table, column, kwargs in comments:
        assert kwargs == {'comment': COLUMN_COMMENTS[table][column]}
