"""Normalize processing table names and document all project database objects."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '20261014_schema_naming_and_comments'
down_revision = '20261004_retire_module_task_demo_jobs'
branch_labels = None
depends_on = None

# Freeze the migration contract rather than importing a mutable runtime map.
_RENAMES = {
    'hp_data_source': 'data_sources', 'hp_domain': 'domains', 'hp_topic': 'topics',
    'hp_news': 'articles', 'sys_prompt_version': 'prompt_versions',
    'act_domain_topic_actions': 'domain_topic_rules',
    'news_prompt_usage': 'prompt_usages', 'news_embedding': 'embeddings',
}


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _apply_comment_file(filename: str) -> None:
    statement = (Path(__file__).resolve().parents[2] / 'sql' / filename).read_text(encoding='utf-8-sig')
    # One server-side block works with asyncpg prepared execution, including
    # guarded optional-object DO blocks, without splitting quoted comments.
    op.get_bind().exec_driver_sql(f'DO $pipesight_documentation$ BEGIN\n{statement}\nEND $pipesight_documentation$;')


def _canonical_constraint_name(name: str, table: str, kind: str) -> str:
    if kind == 'p':
        return f'pk_{table}'
    replacements = {
        'uk_prompt_version': 'uk_prompt_versions_key_version',
        'uk_prompt_content': 'uk_prompt_versions_key_hash',
        'ck_prompt_version_positive': 'ck_prompt_versions_version_positive',
        'ck_prompt_status': 'ck_prompt_versions_status',
        'ck_prompt_hash': 'ck_prompt_versions_hash',
        'ck_prompt_parent': 'ck_prompt_versions_parent',
        'ck_prompt_published_at': 'ck_prompt_versions_published_at',
        'ck_domain_topic_prompt': 'ck_domain_topic_rules_prompt',
        'fk_prompt_usage_news': 'fk_prompt_usages_articles',
        'uk_prompt_usage_sequence': 'uk_prompt_usages_sequence',
        'ck_prompt_usage_sequence': 'ck_prompt_usages_sequence',
        'ck_embedding_version': 'ck_embeddings_version',
        'ck_embedding_hash': 'ck_embeddings_hash',
        'fk_news_embedding_news': 'fk_embeddings_articles',
    }
    if name in replacements:
        return replacements[name]
    for old, new in _RENAMES.items():
        name = name.replace(old, new)
    if name.endswith('_fkey'):
        return f'fk_{name[:-5]}'
    return name


def _normalize_index_names() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("""
        SELECT c.relname AS table_name,k.conname,k.contype::text AS kind
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='news'
        ORDER BY c.relname,k.conname
    """)).mappings().all()
    for row in rows:
        if row['table_name'] not in _RENAMES.values():
            continue
        name = _canonical_constraint_name(row['conname'], row['table_name'], row['kind'])
        if name != row['conname']:
            op.execute(f'ALTER TABLE news.{_identifier(row["table_name"])} RENAME CONSTRAINT {_identifier(row["conname"])} TO {_identifier(name)}')
    rows = bind.execute(sa.text("""
        SELECT t.relname AS table_name,i.relname AS index_name
        FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid
        JOIN pg_class t ON t.oid=x.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname='news' AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid=i.oid)
    """)).mappings().all()
    extra = {
        'uk_prompt_single_published': 'uk_prompt_versions_single_published',
        'idx_prompt_lookup': 'idx_prompt_versions_lookup',
        'idx_prompt_usage_version': 'idx_prompt_usages_version',
        'idx_prompt_usage_news': 'idx_prompt_usages_articles',
        'idx_prompt_usage_news_fk': 'idx_prompt_usages_articles_fk',
    }
    for row in rows:
        if row['table_name'] not in _RENAMES.values():
            continue
        name = extra.get(row['index_name'], _canonical_constraint_name(row['index_name'], row['table_name'], 'index'))
        if name != row['index_name']:
            op.execute(f'ALTER INDEX news.{_identifier(row["index_name"])} RENAME TO {_identifier(name)}')


def _annotate_compatibility_view(view: str, table: str) -> None:
    op.get_bind().exec_driver_sql(f'COMMENT ON VIEW news."{view}" IS {_literal(f"历史名称兼容视图，实际数据位于 news.{table}，新代码及物理表操作使用规范表名")}')
    for column in inspect(op.get_bind()).get_columns(table, schema='news'):
        if not column.get('comment'):
            raise RuntimeError(f'缺少字段注释：news.{table}.{column["name"]}')
        op.get_bind().exec_driver_sql(f'COMMENT ON COLUMN news."{view}".{_identifier(column["name"])} IS {_literal(column["comment"])}')


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    tables = set(inspect(bind).get_table_names(schema='news'))
    for old, new in _RENAMES.items():
        if old in tables:
            if new in tables:
                raise RuntimeError(f'历史表和规范表同时存在，拒绝覆盖：news.{old} / news.{new}')
            op.rename_table(old, new, schema='news')
            tables.remove(old)
            tables.add(new)
        if new not in tables:
            raise RuntimeError(f'缺少处理域基础表 news.{new}，请先执行 insighthub-schema.pg.sql')
        op.execute(f'CREATE OR REPLACE VIEW news."{old}" WITH (security_invoker=true) AS SELECT * FROM news."{new}"')
    _normalize_index_names()
    # Freeze this historical step; later migrations shorten public table names.
    _apply_comment_file('legacy/application-comments-20261014.pg.sql')
    _apply_comment_file('processing-comments-pg.sql')
    for old, new in _RENAMES.items():
        _annotate_compatibility_view(old, new)
    _annotate_compatibility_view('sys_domain', 'domains')


def downgrade() -> None:
    # Documentation is retained. Reverting names is an explicit operator action;
    # legacy read clients already have views and do not need a destructive undo.
    raise RuntimeError('该规范化迁移不自动撤销，请使用已验证的备份或显式改名回退方案')
