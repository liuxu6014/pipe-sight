"""Approved compact schema: fail before changing data when prerequisites are absent."""

# Literal counts assert the approved contracts independently of implementation.
# ruff: noqa: PLR2004

import hashlib
import json

import pytest
from sqlalchemy.dialects import postgresql

from app.business_ids import BUSINESS_ID_TABLES
from app.schema_contract import (
    FOUNDATION_TABLE_RENAMES,
    SchemaPrerequisiteError,
    load_contract,
    validate_target_prerequisites,
)
from app.schema_migration import CONTRACT_SHA256, _contract


def test_v6_adds_only_nullable_schedule_history_and_preserves_every_prior_field():
    old, new = load_contract('v5'), load_contract('v6')
    before = {table['name']:table for table in old['tables']}
    after = {table['name']:table for table in new['tables']}
    assert before.keys() == after.keys()
    extra = {'last_run_at','last_status','last_error'}
    for name, table in before.items():
        if name != 'digest_schedules':
            assert table == after[name]
        else:
            assert table['columns'] == [c for c in after[name]['columns'] if c['name'] not in extra]
            added = [c for c in after[name]['columns'] if c['name'] in extra]
            assert len(added) == 3 and all(c['nullable'] and not c['primary_key'] for c in added)
    assert old['foreign_keys'] == new['foreign_keys']
    assert old['optional_table_definitions'] == new['optional_table_definitions']


def test_contract_has_exact_approved_tables_and_fields() -> None:
    contract = load_contract()
    assert len(contract['tables']) == 27
    assert sum(len(t['columns']) for t in contract['tables']) == 320
    assert {t['name'] for t in contract['tables']} >= {'sys_user', 'papers', 'collection_runs'}
    for table in contract['tables']:
        if table['name'] not in FOUNDATION_TABLE_RENAMES.values():
            assert len(table['name'].split('_')) <= 2
        names = [c['name'] for c in table['columns']]
        assert len(names) == len(set(names))


def test_papers_have_no_full_text_and_single_category_reference() -> None:
    tables = {t['name']: t for t in load_contract()['tables']}
    columns = {c['name'] for c in tables['papers']['columns']}
    assert {'category_id', 'abstract', 'abstract_zh', 'url', 'published_date'} <= columns
    assert not columns & {'content', 'content_zh', 'full_text', 'publication_date'}
    assert 'content_categories' not in tables


def test_v2_changes_exactly_twelve_foundation_names_and_no_fields() -> None:
    v1, v2 = load_contract('v1'), load_contract('v2')
    expected = {'users': 'sys_user', 'roles': 'sys_role', 'menus': 'sys_menu',
        'user_roles': 'sys_user_role', 'role_menus': 'sys_role_menu', 'settings': 'sys_config',
        'dict_types': 'sys_dict_type', 'dict_items': 'sys_dict_data', 'login_logs': 'sys_logininfor',
        'operation_logs': 'sys_oper_log', 'scheduled_jobs': 'sys_job', 'job_logs': 'sys_job_log'}
    assert expected == FOUNDATION_TABLE_RENAMES
    assert v2['version'] == '20261025-compact-v2'
    old, new = {t['name']: t for t in v1['tables']}, {t['name']: t for t in v2['tables']}
    assert len(old) == len(new) == 27
    assert set(new) == {expected.get(n, n) for n in old}
    for name, spec in old.items():
        assert new[expected.get(name, name)]['columns'] == spec['columns']
    changed = [dict(f, table=expected.get(f['table'], f['table']), target=expected.get(f['target'], f['target']))
               for f in v1['foreign_keys']]
    assert v2['foreign_keys'] == changed
    assert v2['optional_tables'] == v1['optional_tables'] == ['model_calls', 'report_versions']
    assert sum(len(t['columns']) for t in new.values()) == 317
    assert {c['name'] for c in new['sys_user']['columns']} >= {'id', 'created_at', 'username', 'password_hash'}


def test_v1_remains_frozen_and_cannot_silently_resolve_to_runtime_v2() -> None:
    value = load_contract('v1')
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert digest == CONTRACT_SHA256 == 'b476a7cb7b9366c6f139ea2fc8318826db5c9d5c8e4402e8884b0cc753170b51'
    assert _contract() == value and 'users' in {t['name'] for t in value['tables']}
    with pytest.raises(ValueError, match='Unsupported'):
        load_contract('../compact-v1')


def test_v2_stays_frozen_when_runtime_default_advances() -> None:
    value = load_contract('v2')
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert digest == 'ce0c17988cdfaaf528315ef1bd8a087bb8959922d50d2e5acd5753385af710fd'


def test_v3_stays_frozen_when_runtime_default_advances() -> None:
    value = load_contract('v3')
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert digest == 'ea009e6a104eb8b54e42e12cb45ae369bb3add9db6a198dcb1343629df635b78'


def test_v4_stays_frozen_when_beijing_audit_runtime_v5_becomes_default() -> None:
    value = load_contract('v4')
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert digest == '88491613e027bcdc0058837512053d68eae7a757d9ebcadad16e46e92316b8bc'
    assert load_contract() == load_contract('v6')
    assert load_contract()['version'] == '20261028-compact-v6'


def test_v4_preserves_v3_physical_core_without_freezing_unstable_orm_ddl() -> None:
    v3, v4 = load_contract('v3'), load_contract('v4')
    for key in ('tables', 'optional_tables', 'optional_table_definitions', 'foreign_keys',
                'optional_foreign_keys', 'sequences'):
        assert v4[key] == v3[key], key
    assert len(v4['tables']) == 27 and len(v4['optional_table_definitions']) == 2
    assert sum(len(t['columns']) for t in v4['tables'] + v4['optional_table_definitions']) == 340
    assert len(v4['foreign_keys']) + len(v4['optional_foreign_keys']) == 35
    policy = v4['business_ddl_policy']
    assert policy['status'] == 'separate-artifact-required'
    assert policy['physical_core'] == 'identical-to-compact-v3'
    assert policy['absent_column_default'] == 'unspecified-not-no-default'
    assert policy['startup_guard_owner'] == 'main'
    assert set(policy['startup_compare']) == {
        'table_inventory', 'column_inventory', 'types', 'nullable', 'primary_keys',
        'foreign_keys', 'server_defaults', 'identity', 'sequences', 'indices', 'checks',
    }
    assert not {'indices', 'checks', 'identities'} & v4.keys()


def test_v4_distinguishes_opaque_values_from_explicit_semantic_references() -> None:
    policy = load_contract('v4')['business_id_policy']
    v3 = load_contract('v3')['business_id_policy']
    for key in ('tables', 'sql_type', 'sequence', 'server_default', 'wire_format', 'minimum', 'maximum'):
        assert policy[key] == v3[key]
    assert 'unchanged_payload_fields' not in policy and policy['json_payloads'] != 'preserve'
    assert policy['opaque_values']['ordinary_request_id'] == 'preserve-exact'
    assert policy['opaque_values']['execution_token'] == 'preserve-exact'
    rules = {(rule['table'], rule['kind']): rule for rule in policy['system_request_keys']}
    assert set(rules) == {('generation_tasks', 'schedule'), ('collection_runs', 'schedule'),
                          ('collection_runs', 'retry')}
    assert rules['generation_tasks', 'schedule']['reference_column'] == 'schedule_id'
    assert rules['collection_runs', 'schedule']['reference_column'] == 'source_id'
    assert rules['collection_runs', 'retry']['reference_column'] == 'parent_id'
    assert all(rule['rewrite'] == 'mapped-reference-only-preserve-other-bytes' for rule in rules.values())
    refs = policy['json_references']
    assert refs['wire_format'] == 'decimal-string'
    assert refs['unmapped_or_ambiguous'] == 'reject-before-write'
    assert refs['scalar_keys']['report_id'] == refs['scalar_keys']['reportId'] == 'reports'
    assert refs['list_keys']['category_ids'] == 'categories'
    assert refs['typed_item_id']['requires_entity_context'] is True
    assert refs['opaque_precedence'] == 'declared-free-text-and-external-values-before-key-matching'
    fingerprint = policy['semantic_fingerprints']
    assert fingerprint['generation_tasks.config_snapshot.request_fingerprint']['action'] == 'recompute-from-mapped-request-and-materials'
    assert fingerprint['generation_tasks.config_snapshot.request_fingerprint']['algorithm'] == 'app.business_ids.generation_request_fingerprint'
    assert policy['verification']['retain_mapping_and_rewrite_audit'] is True
    assert policy['verification']['compare_all_nonreference_values'] == 'exact'


def test_v4_points_to_main_owned_business_snapshot_without_duplicating_ddl() -> None:
    contract = load_contract('v4')
    assert contract['runtime_version'] == 'v4'
    assert contract['business_schema_snapshot'] == 'business-v4.json'
    assert contract['version'] == '20261025-compact-' + contract['runtime_version']
    assert contract['business_ddl_policy']['snapshot_sections'] == ['model_ddl', 'catalog']
    assert not {'model_ddl', 'catalog'} & contract.keys()
    assert not {'model_ddl', 'catalog'} & contract['business_ddl_policy'].keys()
    # This artifact is generated/frozen by main only after isolated-reference
    # parity; loading the policy must not import ORM or require an unfrozen file.
    for version in ('v1', 'v2', 'v3'):
        assert 'business_schema_snapshot' not in load_contract(version)


def test_v5_changes_only_the_27_business_audit_column_types() -> None:
    v4, v5 = load_contract('v4'), load_contract('v5')
    assert v5['runtime_version'] == 'v5'
    assert v5['business_schema_snapshot'] == 'business-v5.json'
    for key in ('optional_tables', 'foreign_keys', 'optional_foreign_keys', 'sequences', 'business_id_policy'):
        assert v5[key] == v4[key], key
    business = {*BUSINESS_ID_TABLES, 'ai_models', 'basket_items', 'report_versions'}
    changed = set()
    for group in ('tables', 'optional_table_definitions'):
        before = {t['name']: t for t in v4[group]}
        after = {t['name']: t for t in v5[group]}
        assert set(before) == set(after)
        for name, table in before.items():
            assert len(after[name]['columns']) == len(table['columns'])
            for old, new in zip(table['columns'], after[name]['columns'], strict=True):
                expected = dict(old)
                if name in business and old['name'] in ('created_at', 'updated_at'):
                    expected['type'] = 'timestamp(0) without time zone'
                    changed.add((name, old['name']))
                assert new == expected, (name, old['name'])
    assert len(changed) == 27
    assert len({name for name, column in changed if column == 'created_at'}) == 15
    assert len({name for name, column in changed if column == 'updated_at'}) == 12
    policy = v5['audit_timestamp_policy']
    assert set(policy['tables']) == business
    assert {tuple(pair) for pair in policy['fields']} == changed
    assert policy['field_count'] == 27


def test_v5_beijing_timestamp_policy_is_explicit_and_dialect_ddl_is_second_precision() -> None:
    policy = load_contract('v5')['audit_timestamp_policy']
    assert policy['sql_type'] == 'timestamp(0) without time zone'
    assert policy['timezone'] == 'Asia/Shanghai'
    assert policy['with_timezone'] is False and policy['precision'] == 0
    assert policy['api_format'] == policy['page_format'] == 'YYYY-MM-DD HH:mm:ss'
    assert policy['storage_semantics'] == 'Beijing-local-wall-clock'
    assert policy['source_conversion'] == 'source-instant-AT-TIME-ZONE-Asia/Shanghai-before-precision-reduction'
    assert policy['operational_timestamps'] == 'unchanged-timestamptz'
    assert policy['foundation_timestamps'] == 'unchanged'
    sql_type = postgresql.TIMESTAMP(precision=policy['precision'], timezone=policy['with_timezone'])
    assert sql_type.compile(dialect=postgresql.dialect()).lower() == policy['sql_type']


def test_v3_exactly_twelve_business_primary_keys_share_bigint_sequence() -> None:
    contract = load_contract('v3')
    expected = {'categories', 'collection_runs', 'data_sources', 'digest_schedules', 'generation_tasks',
                'knowledge_files', 'model_calls', 'news_articles', 'papers', 'report_assets', 'reports', 'templates'}
    assert set(BUSINESS_ID_TABLES) == expected == set(contract['business_id_policy']['tables'])
    tables = {t['name']: t for t in contract['tables'] + contract['optional_table_definitions']}
    assert len(tables) == 29 and sum(len(t['columns']) for t in tables.values()) == 340
    sequence = contract['sequences']
    assert len(sequence) == 1 and sequence[0]['name'] == 'business_id_seq'
    assert sequence[0]['schema'] == 'public' and sequence[0]['owned_by'] is None
    assert set(sequence[0]['shared_by']) == expected
    for table in expected:
        pk = [c for c in tables[table]['columns'] if c['primary_key']]
        assert len(pk) == 1 and pk[0]['name'] == 'id' and pk[0]['type'] == 'bigint'
        assert pk[0]['server_default'] == "nextval('business_id_seq'::regclass)"
    generated = {t['name'] for t in tables.values() for c in t['columns'] if c.get('server_default')}
    assert generated == expected
    assert contract['business_id_policy']['wire_format'] == 'decimal-string'
    assert int(contract['business_id_policy']['maximum']) == 2**63 - 1
    assert contract['business_id_policy']['minimum'] == 1


def test_v3_all_fk_types_match_and_payload_identifiers_are_not_numericized() -> None:
    v2, v3 = load_contract('v2'), load_contract('v3')
    before = {t['name']: t for t in v2['tables']}
    after = {t['name']: t for t in v3['tables'] + v3['optional_table_definitions']}
    numeric = set(v3['business_id_policy']['tables'])
    fks = v3['foreign_keys'] + v3['optional_foreign_keys']
    assert len(fks) == 35
    referenced = set()
    for fk in fks:
        for col, dest in zip(fk['columns'], fk['target_columns'], strict=True):
            a = next(c for c in after[fk['table']]['columns'] if c['name'] == col)
            b = next(c for c in after[fk['target']]['columns'] if c['name'] == dest)
            assert a['type'] == b['type'], (fk['table'], col)
            if fk['target'] in numeric:
                assert a['type'] == 'bigint'
                referenced.add((fk['table'], col))
    assert {('report_versions', 'report_id'), ('model_calls', 'task_id')} <= referenced
    for name, table in before.items():
        assert len(after[name]['columns']) == len(table['columns'])
        for old, new in zip(table['columns'], after[name]['columns'], strict=True):
            expected = dict(old)
            if old['type'] == 'ID':
                expected['type'] = 'varchar(64)'
            if name in numeric and old['primary_key']:
                expected.update(type='bigint', server_default="nextval('business_id_seq'::regclass)")
            if (name, old['name']) in referenced:
                expected['type'] = 'bigint'
            assert new == expected
    for name in ('collection_runs', 'generation_tasks'):
        cols = {c['name']: c for c in after[name]['columns']}
        assert cols['execution_token']['type'] == 'varchar(64)'
        assert cols['request_id']['type'] == 'varchar(128)'
    assert all(c['type'] != 'ID' for t in after.values() for c in t['columns'])


def test_missing_models_preserves_templates_without_inventing_model_ids() -> None:
    result = validate_target_prerequisites(
        templates=[{'template_id': 'existing-template', 'name': 'Existing'}], models=[],
    )
    assert result['default_text_model_id'] is None
    assert result['generation_ready'] is False


def test_image_model_does_not_silently_become_template_text_model() -> None:
    result = validate_target_prerequisites(
        templates=[{'template_id': 'existing-template'}],
        models=[{'id': 1, 'capabilities': ['image_generate'], 'is_enabled': True}],
    )
    assert result['default_text_model_id'] is None
    assert result['generation_ready'] is False


def test_valid_text_model_can_satisfy_single_model_template_prerequisite() -> None:
    result = validate_target_prerequisites(
        templates=[{'template_id': 'existing-template'}],
        models=[{'id': 1, 'capabilities': ['text_generate'], 'is_enabled': True}],
    )
    assert result['default_text_model_id'] == 1


def test_multiple_text_models_require_explicit_template_mapping() -> None:
    with pytest.raises(SchemaPrerequisiteError, match='选择'):
        validate_target_prerequisites(
            templates=[{'template_id': 'existing-template'}],
            models=[{'id': n, 'capabilities': ['text_generate'], 'is_enabled': True} for n in (1, 2)],
        )
