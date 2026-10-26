"""Retire unused processing aliases after canonical runtime SQL deployment."""

import sqlalchemy as sa
from alembic import op

revision = '20261025_retire_processing_views'
down_revision = '20261014_semantic_business_names'
branch_labels = None
depends_on = None

# Frozen contract: never derive destructive targets from mutable runtime maps.
VIEWS = {
    'sys_domain': 'domains',
    'hp_data_source': 'data_sources',
    'hp_domain': 'domains',
    'hp_topic': 'topics',
    'hp_news': 'articles',
    'sys_prompt_version': 'prompt_versions',
    'act_domain_topic_actions': 'domain_topic_rules',
    'news_prompt_usage': 'prompt_usages',
    'news_embedding': 'embeddings',
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        raise RuntimeError('This migration requires PostgreSQL')
    present = []
    # Complete preflight before the first DROP. Never drop physical tables or
    # aliases that have been repurposed to point at unrelated objects.
    for view, target in VIEWS.items():
        name = f'news.{view}'
        kind = bind.execute(sa.text('SELECT relkind::text FROM pg_class WHERE oid=to_regclass(:name)'), {'name': name}).scalar_one_or_none()
        if kind is None:
            continue
        if kind != 'v':
            raise RuntimeError(f'Refusing to remove non-view object: {name}')
        sources = bind.execute(sa.text("""
            SELECT DISTINCT n.nspname || '.' || t.relname
            FROM pg_rewrite r JOIN pg_depend d ON d.classid='pg_rewrite'::regclass AND d.objid=r.oid
            JOIN pg_class t ON d.refclassid='pg_class'::regclass AND d.refobjid=t.oid
            JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE r.ev_class=to_regclass(:name) AND t.oid<>r.ev_class
        """), {'name': name}).scalars().all()
        if set(sources) != {f'news.{target}'}:
            raise RuntimeError(f'Unexpected view sources for {name}: {sources}')
        present.append(view)
    for view in present:
        # RESTRICT intentionally aborts the transaction for unexpected dependents.
        bind.exec_driver_sql(f'DROP VIEW news."{view}" RESTRICT')
    bind.exec_driver_sql("COMMENT ON TABLE news.domains IS '资讯领域定义与处理器配置；配置服务直接读取 domains 中未删除记录，内嵌过滤和评分提示词由当前动态领域处理器使用。'")


def downgrade() -> None:
    bind = op.get_bind()
    for view, target in VIEWS.items():
        bind.exec_driver_sql(f'CREATE VIEW news."{view}" WITH (security_invoker=true) AS SELECT * FROM news."{target}"')
        bind.exec_driver_sql(f"COMMENT ON VIEW news.\"{view}\" IS '历史名称兼容视图，实际数据位于 news.{target}'")
    bind.exec_driver_sql('GRANT SELECT ON news.sys_domain TO news_app')
