"""Only equivalent PG deparser text-array spelling may compare equal."""

from copy import deepcopy

import pytest

from app.numeric_id_migration import _constraint_signature, _index_signature, canonical_catalog_sql

OLD_ARRAY = "ARRAY['queued'::character varying, 'running'::character varying]::text[]"
NEW_ARRAY = "ARRAY['queued'::text, 'running'::text]"


def wrap(expression: str, kind: str) -> str:
    if kind == 'constraint':
        return 'CHECK ((status = ANY (' + expression + ')))'
    return (
        'CREATE UNIQUE INDEX run_active ON public.collection_runs USING btree (source_id) WHERE (status = ANY ('
        + expression
        + '))'
    )


@pytest.mark.parametrize('kind', ['constraint', 'partial_index'])
@pytest.mark.parametrize(
    'variant',
    [
        NEW_ARRAY,
        "(ARRAY['queued'::text, 'running'::text])",
        "((ARRAY[('queued'::character varying)::text, ('running'::character varying)::text]))",
        "(ARRAY[(('queued')::text), (('running')::text)])::text[]",
        "((ARRAY[(('queued'::character varying)), (('running'::character varying))])::text[])",
    ],
)
def test_pg184_and_pg186_text_array_spellings_are_equivalent(kind: str, variant: str) -> None:
    assert canonical_catalog_sql(wrap(OLD_ARRAY, kind)) == canonical_catalog_sql(wrap(variant, kind))


@pytest.mark.parametrize('quantifier', ['ANY', 'ALL'])
@pytest.mark.parametrize(
    'literal',
    [
        "'queued, running'",
        "'can''t wait'",
        "'quoted '') , ( value'",
        "''",
        "'中文,状态'",
        "'a]b[c'",
    ],
)
def test_literal_commas_quotes_and_parentheses_are_not_token_separators(quantifier: str, literal: str) -> None:
    old = f"CHECK (status = {quantifier} (ARRAY[{literal}::character varying, 'ok'::character varying]::text[]))"
    new = f"CHECK (status = {quantifier} (ARRAY[(({literal})::text), ('ok'::text)]))"
    assert canonical_catalog_sql(old) == canonical_catalog_sql(new)
    assert literal in canonical_catalog_sql(old)


@pytest.mark.parametrize('kind', ['constraint', 'partial_index'])
@pytest.mark.parametrize(
    'change', ['enum', 'operator', 'column', 'quantifier', 'integer_array', 'enum_cast', 'varchar_limit']
)
def test_semantically_different_definitions_cannot_compare_equal(kind: str, change: str) -> None:
    old = wrap(OLD_ARRAY, kind)
    changed = wrap(NEW_ARRAY, kind)
    if change == 'enum':
        changed = changed.replace("'running'", "'failed'")
    elif change == 'operator':
        changed = changed.replace('status = ANY', 'status <> ANY')
    elif change == 'column':
        changed = changed.replace('status = ANY', 'other_status = ANY')
    elif change == 'quantifier':
        changed = changed.replace('ANY', 'ALL')
    elif change == 'integer_array':
        changed = wrap('ARRAY[1, 2]::integer[]', kind)
    elif change == 'enum_cast':
        changed = wrap("ARRAY['queued'::run_state, 'running'::run_state]::text[]", kind)
    else:
        changed = wrap("ARRAY['queued'::character varying(2), 'running'::character varying(2)]::text[]", kind)
    assert canonical_catalog_sql(old) != canonical_catalog_sql(changed)


@pytest.mark.parametrize(
    'array',
    [
        'ARRAY[1, 2]::integer[]',
        "ARRAY['1'::integer, '2'::integer]::text[]",
        "ARRAY[current_setting('state')]::text[]",
        "ARRAY[status::text, 'queued'::text]",
        "ARRAY['queued'::run_state, 'running'::run_state]::text[]",
        "ARRAY['queued'::character varying(2)]::text[]",
    ],
)
def test_nonliteral_or_nontext_cast_arrays_are_left_untouched(array: str) -> None:
    sql = wrap(array, 'constraint')
    assert canonical_catalog_sql(sql) == sql


@pytest.mark.parametrize('quote', ['single', 'identifier', 'dollar', 'tagged_dollar'])
def test_sql_inside_quoted_text_is_never_normalized(quote: str) -> None:
    def quoted(value: str) -> str:
        if quote == 'single':
            return "'" + value.replace("'", "''") + "'"
        if quote == 'identifier':
            return '"' + value.replace('"', '""') + '"'
        delimiter = '$tag$' if quote == 'tagged_dollar' else '$$'
        return delimiter + value + delimiter

    old = 'CHECK (note <> ' + quoted('ANY (' + OLD_ARRAY + ')') + ')'
    changed = 'CHECK (note <> ' + quoted('ANY (' + NEW_ARRAY + ')') + ')'
    assert canonical_catalog_sql(old) == old
    assert canonical_catalog_sql(changed) == changed
    assert canonical_catalog_sql(old) != canonical_catalog_sql(changed)


def test_constraint_signatures_only_normalize_definition_without_mutating_source() -> None:
    old = [
        {
            'table_name': 'collection_runs',
            'name': 'ck_run_status',
            'type': 'c',
            'definition': wrap(OLD_ARRAY, 'constraint'),
            'validated': True,
        }
    ]
    new = deepcopy(old)
    new[0]['definition'] = wrap(NEW_ARRAY, 'constraint')
    before = deepcopy(old)
    assert _constraint_signature(old) == _constraint_signature(new)
    assert old == before
    for key, value in [('table_name', 'other'), ('name', 'other'), ('type', 'f'), ('validated', False)]:
        changed = deepcopy(new)
        changed[0][key] = value
        assert _constraint_signature(old) != _constraint_signature(changed)


def test_partial_index_signatures_keep_identity_uniqueness_and_validity() -> None:
    old = [('collection_runs', 'run_active', wrap(OLD_ARRAY, 'partial_index'), True, True)]
    new = [('collection_runs', 'run_active', wrap(NEW_ARRAY, 'partial_index'), True, True)]
    assert _index_signature(old) == _index_signature(new)
    for position, value in [(0, 'other_table'), (1, 'other_index'), (3, False), (4, False)]:
        row = list(new[0])
        row[position] = value
        assert _index_signature(old) != _index_signature([tuple(row)])


@pytest.mark.parametrize(
    'sql',
    [
        "CHECK (MYANY(ARRAY['queued'::text]))",
        "CHECK (status = ANY (ARRAY['queued'::integer]))",
        "CHECK (status = ANY (ARRAY['queued'::text]",
        "CHECK (note = 'unterminated ANY (ARRAY[''queued''::text])",
    ],
)
def test_nonmatching_or_malformed_fragments_are_preserved(sql: str) -> None:
    assert canonical_catalog_sql(sql) == sql


def test_normalization_is_idempotent() -> None:
    sql = wrap(OLD_ARRAY, 'partial_index')
    once = canonical_catalog_sql(sql)
    assert canonical_catalog_sql(once) == once
