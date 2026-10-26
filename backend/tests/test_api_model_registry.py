from app.bootstrap import create_app
from config.database import Base


def test_api_bootstrap_registers_cross_boundary_models() -> None:
    create_app()

    tables = Base.metadata.tables
    assert {'sys_user', 'sys_job', 'news_articles', 'knowledge_files', 'categories'}.issubset(tables)
    assert not {'users', 'scheduled_jobs', 'content_review_events', 'model_routes', 'prompt_versions'} & set(tables)
    expected = {
        ('news_articles', 'category_id'): ('categories.id', 'RESTRICT'),
        ('news_articles', 'source_id'): ('data_sources.id', 'RESTRICT'),
        ('knowledge_files', 'user_id'): ('sys_user.id', 'RESTRICT'),
        ('collection_runs', 'source_id'): ('data_sources.id', 'RESTRICT'),
        ('sys_job_log', 'job_id'): ('sys_job.id', 'SET NULL'),
    }
    for (table_name, column_name), relation in expected.items():
        foreign_keys = tables[table_name].c[column_name].foreign_keys
        assert relation in {(foreign_key.target_fullname, foreign_key.ondelete) for foreign_key in foreign_keys}
    assert 'reviewed_by' not in tables['news_articles'].c
    assert 'scheduler_job_id' not in tables['collection_runs'].c
    for table in tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table.key in tables
