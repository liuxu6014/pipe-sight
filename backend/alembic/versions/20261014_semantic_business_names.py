"""Restore necessary business meaning in four overly abbreviated table names."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '20261014_semantic_business_names'
down_revision = '20261014_short_business_table_names'
branch_labels = None
depends_on = None

# Frozen migration contract, independent of mutable runtime declarations.
RENAMES = {
    'review_events': 'content_review_events',
    'duplicate_events': 'duplicate_group_events',
    'route_usage': 'model_route_usage',
    'quality_events': 'quality_issue_events',
}


def identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def short_name(name: str) -> str:
    # Existing semantic index names (e.g. idx_model_route_usage_date) already
    # include the domain; never blindly replace substrings within these names.
    for old, new in RENAMES.items():
        if name == f'{old}_pkey':
            return f'{new}_pkey'
    return name


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        raise RuntimeError('This migration requires the project PostgreSQL database')
    inspector = inspect(bind)
    tables = set(inspector.get_table_names(schema='public'))
    objects = tables | set(inspector.get_view_names(schema='public'))
    # Validate the entire mapping before changing anything; never merge objects.
    for old, new in RENAMES.items():
        if old in tables and new in objects:
            raise RuntimeError(f'Both objects exist: public.{old} / public.{new}')
        if old not in tables and new not in tables:
            raise RuntimeError(f'Missing business table: public.{old} / public.{new}')
    for old, new in RENAMES.items():
        if old in tables:
            op.rename_table(old, new, schema='public')

    constraints = bind.execute(sa.text("""
      SELECT t.relname AS table_name,k.conname
      FROM pg_constraint k JOIN pg_class t ON t.oid=k.conrelid
      JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public'
    """)).mappings().all()
    for row in constraints:
        if row['table_name'] not in RENAMES.values():
            continue
        name = short_name(row['conname'])
        if name != row['conname']:
            bind.exec_driver_sql(f'ALTER TABLE public.{identifier(row["table_name"])} RENAME CONSTRAINT {identifier(row["conname"])} TO {identifier(name)}')
    indexes = bind.execute(sa.text("""
      SELECT t.relname AS table_name,i.relname AS index_name
      FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid
      JOIN pg_class t ON t.oid=x.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
      WHERE n.nspname='public' AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid=i.oid)
    """)).mappings().all()
    for row in indexes:
        if row['table_name'] not in RENAMES.values():
            continue
        name = short_name(row['index_name'])
        if name != row['index_name']:
            bind.exec_driver_sql(f'ALTER INDEX public.{identifier(row["index_name"])} RENAME TO {identifier(name)}')
    source = (Path(__file__).resolve().parents[2] / 'sql/application-comments-pg.sql').read_text(encoding='utf-8-sig')
    bind.exec_driver_sql(f'DO $short_names_comments$ BEGIN\n{source}\nEND $short_names_comments$;')


def downgrade() -> None:
    raise RuntimeError('Restore the verified backup or use a reviewed explicit rename rollback')
