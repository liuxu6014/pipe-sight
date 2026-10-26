"""Offline completeness and SQL-safety checks; never import or connect to the app DB."""

import re
from pathlib import Path

import pytest

SQL_DIR = Path(__file__).resolve().parents[1] / 'sql'
SCHEMA_SQL = SQL_DIR / 'insighthub-schema.pg.sql'
COMMENTS_SQL = SQL_DIR / 'processing-comments-pg.sql'
MIN_CHINESE_CHARACTERS = 8
TABLE_NAMES = {
    'hp_data_source': 'data_sources',
    'hp_domain': 'domains',
    'hp_topic': 'topics',
    'hp_news': 'articles',
    'sys_prompt_version': 'prompt_versions',
    'act_domain_topic_actions': 'domain_topic_rules',
    'news_prompt_usage': 'prompt_usages',
    'news_embedding': 'embeddings',
}
IDENTIFIER = r'(?:"(?:[^"]|"")+"|[a-z_][a-z0-9_]*)'
COMMENT = re.compile(
    rf'COMMENT\s+ON\s+(SCHEMA|TABLE|COLUMN)\s+({IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})*)'
    r"\s+IS\s+'((?:[^']|'')*)'\s*;",
    re.IGNORECASE,
)
TRIVIA = re.compile(r'(?:\s+|--[^\n]*(?:\n|$))*')


def _comments(sql: str) -> dict[tuple[str, tuple[str, ...]], str]:
    """Accept only complete COMMENT statements, preserving quotes inside strings."""
    result = {}
    offset = 0
    while offset < len(sql):
        offset = TRIVIA.match(sql, offset).end()
        if offset == len(sql):
            break
        statement = COMMENT.match(sql, offset)
        assert statement is not None, f'Not a pure COMMENT statement at offset {offset}: {sql[offset : offset + 100]!r}'
        kind, qualified, text = statement.groups()
        identifiers = tuple(
            part[1:-1].replace('""', '"') if part.startswith('"') else part.lower()
            for part in re.findall(IDENTIFIER, qualified, flags=re.IGNORECASE)
        )
        key = kind.upper(), identifiers
        assert key not in result, f'Duplicate comment target: {key}'
        result[key] = text.replace("''", "'")
        offset = statement.end()
    assert result, 'No COMMENT statements found'
    return result


def _definitions(body: str) -> list[str]:
    """Split top-level DDL entries, not commas inside types, checks or literals."""
    entries = []
    start = depth = offset = 0
    quote = None
    while offset < len(body):
        char = body[offset]
        if quote:
            if char == quote:
                if offset + 1 < len(body) and body[offset + 1] == quote:
                    offset += 1
                else:
                    quote = None
        elif char in '\'"':
            quote = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            entries.append(body[start:offset].strip())
            start = offset + 1
        offset += 1
    assert quote is None and depth == 0, 'Unbalanced reference table definition'
    entries.append(body[start:].strip())
    return entries


def _tables(sql: str) -> dict[str, tuple[dict[str, str], list[str]]]:
    result = {}
    old_names = {canonical: old for old, canonical in TABLE_NAMES.items()}
    for match in re.finditer(
        r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+news\.([a-z_][a-z0-9_]*)\s*\((.*?)\n\);',
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        columns = {}
        constraints = []
        for definition in _definitions(match.group(2)):
            name = re.match(rf'({IDENTIFIER})\s+', definition, flags=re.IGNORECASE)
            assert name, f'Unrecognized DDL entry: {definition}'
            column = name.group(1).strip('"')
            if column.upper() in {'CONSTRAINT', 'PRIMARY', 'UNIQUE', 'CHECK', 'FOREIGN', 'EXCLUDE', 'LIKE'}:
                constraints.append(definition)
            else:
                assert column not in columns, f'Duplicate reference column: {column}'
                columns[column] = definition[name.end() :]
        # The parent migration may rename these DDL targets concurrently. Both
        # spellings must still cover precisely the original, unrenamed columns.
        old = old_names.get(match.group(1), match.group(1))
        assert old not in result, f'Duplicate physical table definition: {old}'
        result[old] = columns, constraints
    assert set(result) == set(TABLE_NAMES), f'Reference table set changed: {set(result) ^ set(TABLE_NAMES)}'
    return result


def _coverage(sql: str, schema: str) -> dict[tuple[str, tuple[str, ...]], str]:
    comments = _comments(sql)
    tables = _tables(schema)
    expected = {('TABLE', ('news', name)) for name in TABLE_NAMES.values()}
    expected.update(
        ('COLUMN', ('news', TABLE_NAMES[old], column)) for old, (columns, _) in tables.items() for column in columns
    )
    actual = {key for key in comments if key[0] != 'SCHEMA'}
    assert actual == expected, f'Missing: {sorted(expected - actual)}; unexpected: {sorted(actual - expected)}'
    schemas = {key for key in comments if key[0] == 'SCHEMA'}
    assert schemas <= {('SCHEMA', ('news',))}, f'Unexpected schema comment: {schemas}'
    return comments


def test_all_eight_canonical_tables_and_every_original_column_are_commented() -> None:
    _coverage(COMMENTS_SQL.read_text(encoding='utf-8'), SCHEMA_SQL.read_text(encoding='utf-8'))


def test_coverage_accepts_old_name_mapping_and_canonical_ddl() -> None:
    schema = SCHEMA_SQL.read_text(encoding='utf-8')
    original = schema
    canonical = schema
    for old, new in TABLE_NAMES.items():
        original = re.sub(rf'\bnews\.{new}\b', f'news.{old}', original)
        canonical = re.sub(rf'\bnews\.{old}\b', f'news.{new}', canonical)
    sql = COMMENTS_SQL.read_text(encoding='utf-8')
    assert _coverage(sql, original) == _coverage(sql, canonical)


@pytest.mark.parametrize(('old', 'canonical'), TABLE_NAMES.items())
def test_each_table_preserves_original_column_names_and_timestamp_types(old: str, canonical: str) -> None:
    comments = _comments(COMMENTS_SQL.read_text(encoding='utf-8'))
    columns, _ = _tables(SCHEMA_SQL.read_text(encoding='utf-8'))[old]
    actual = {target[2] for kind, target in comments if kind == 'COLUMN' and target[:2] == ('news', canonical)}
    assert actual == set(columns)
    for column, definition in columns.items():
        text = comments['COLUMN', ('news', canonical, column)]
        if definition.startswith('timestamp without time zone'):
            assert 'timestamp without time zone' in text
        elif definition.startswith('timestamp with time zone'):
            assert 'timestamp with time zone' in text
        elif definition.startswith('jsonb'):
            assert 'jsonb' in text.lower()


def test_comments_explain_check_enumerations_and_source_format_enum() -> None:
    schema = SCHEMA_SQL.read_text(encoding='utf-8')
    comments = _comments(COMMENTS_SQL.read_text(encoding='utf-8'))
    for old, (columns, constraints) in _tables(schema).items():
        for definition in [*columns.values(), *constraints]:
            for column, values in re.findall(r'\b([a-z_]+)\s+IN\s*\(([^)]+)\)', definition, flags=re.IGNORECASE):
                text = comments['COLUMN', ('news', TABLE_NAMES[old], column)]
                for value in re.findall(r"'([^']+)'", values):
                    assert re.search(rf'(?<![a-z0-9_]){re.escape(value)}(?![a-z0-9_])', text), (old, column, value)
    enum = re.search(r'CREATE TYPE news\.content_type AS ENUM\s*\(([^)]+)\)', schema)
    assert enum
    source_format = comments['COLUMN', ('news', 'data_sources', 'content_type')]
    for value in re.findall(r"'([^']+)'", enum.group(1)):
        assert value in source_format


def test_comments_reference_actual_foreign_keys_using_canonical_table_names() -> None:
    comments = _comments(COMMENTS_SQL.read_text(encoding='utf-8'))
    for old, (columns, constraints) in _tables(SCHEMA_SQL.read_text(encoding='utf-8')).items():
        for column, definition in columns.items():
            reference = re.search(r'REFERENCES\s+news\.([a-z_]+)', definition, flags=re.IGNORECASE)
            if reference:
                canonical = TABLE_NAMES.get(reference.group(1), reference.group(1))
                assert f'news.{canonical}' in comments['COLUMN', ('news', TABLE_NAMES[old], column)]
        for constraint in constraints:
            reference = re.search(
                r'FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES\s+news\.([a-z_]+)', constraint, flags=re.IGNORECASE
            )
            if reference:
                for column in reference.group(1).split(','):
                    canonical = TABLE_NAMES.get(reference.group(2), reference.group(2))
                    assert f'news.{canonical}' in comments['COLUMN', ('news', TABLE_NAMES[old], column.strip())]


def test_every_comment_is_meaningful_chinese_without_placeholder_text() -> None:
    for target, text in _comments(COMMENTS_SQL.read_text(encoding='utf-8')).items():
        assert len(re.findall(r'[\u4e00-\u9fff]', text)) >= MIN_CHINESE_CHARACTERS, (target, text)
        assert not re.search(r'待补充|待完善|占位|TODO|TBD|FIXME', text, flags=re.IGNORECASE), (target, text)


def test_runtime_semantics_are_not_replaced_with_historical_design_claims() -> None:
    comments = _comments(COMMENTS_SQL.read_text(encoding='utf-8'))
    assert 'uuid4().hex[:26]' in comments['COLUMN', ('news', 'articles', 'prompt_trace_id')]
    assert '不是 ULID' in comments['COLUMN', ('news', 'articles', 'prompt_trace_id')]
    assert '尚未写入本表' in comments['TABLE', ('news', 'prompt_usages')]
    assert '尚未解引用' in comments['COLUMN', ('news', 'domain_topic_rules', 'prompt_version_id')]
    assert 'systemPrompts' in comments['COLUMN', ('news', 'domains', 'filter_prompts')]
    assert 'userPrompts' in comments['COLUMN', ('news', 'domains', 'score_prompts')]
    assert 'article.metadata_json' in comments['COLUMN', ('news', 'articles', 'news_all_info')]
    assert '1024' in comments['COLUMN', ('news', 'embeddings', 'embedding')]
    assert 'SHA-256' in comments['COLUMN', ('news', 'embeddings', 'source_hash')]


def test_parser_preserves_escaped_sql_quotes_and_quoted_timestamp_identifier() -> None:
    comments = _comments(
        '-- 注释中的分号不形成语句；\n'
        'COMMENT ON COLUMN news.articles."timestamp" IS '
        "'历史 ''timestamp'' 时间字段；保留字符串内的分号; 和 -- 文本。';\n"
    )
    assert (
        comments['COLUMN', ('news', 'articles', 'timestamp')]
        == "历史 'timestamp' 时间字段；保留字符串内的分号; 和 -- 文本。"
    )


@pytest.mark.parametrize(
    'sql',
    [
        'CREATE TABLE news.unexpected (id bigint);',
        'ALTER TABLE news.articles ADD COLUMN unexpected text;',
        'DROP TABLE news.articles;',
        'BEGIN; COMMIT;',
        '\\set ON_ERROR_STOP on',
        'COMMENT ON TABLE news.articles IS NULL;',
        "COMMENT ON TABLE news.articles IS '未正确结束的字符串;",
        "COMMENT ON TABLE news.articles IS '中文说明'; DELETE FROM news.articles;",
    ],
)
def test_parser_rejects_non_comment_statements_and_invalid_quoting(sql: str) -> None:
    with pytest.raises(AssertionError, match='Not a pure COMMENT statement'):
        _comments(sql)


def test_missing_duplicate_unknown_and_new_reference_columns_fail_coverage() -> None:
    sql = COMMENTS_SQL.read_text(encoding='utf-8')
    schema = SCHEMA_SQL.read_text(encoding='utf-8')
    target = re.search(r"COMMENT ON COLUMN news\.articles\.original_text IS\s+'(?:[^']|'')*'\s*;", sql)
    assert target
    with pytest.raises(AssertionError, match=r'Missing:.*original_text'):
        _coverage(sql[: target.start()] + sql[target.end() :], schema)
    with pytest.raises(AssertionError, match='Duplicate comment target'):
        _coverage(sql + '\n' + target.group(0), schema)
    with pytest.raises(AssertionError, match=r'unexpected:.*not_a_column'):
        _coverage(
            sql + "\nCOMMENT ON COLUMN news.articles.not_a_column IS '不存在的字段不能误计入注释覆盖率。';", schema
        )
    with pytest.raises(AssertionError, match=r'Missing:.*future_column'):
        _coverage(sql, schema.replace('    original_text text,', '    original_text text,\n    future_column text,'))
