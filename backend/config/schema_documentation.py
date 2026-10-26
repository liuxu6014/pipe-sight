"""Stable naming and documentation contract for PostgreSQL-owned objects.

Framework tables retain RuoYi names. Business tables use short descriptive
names; processing legacy names remain available as compatibility views.
"""

from sqlalchemy import Table

PROCESSING_TABLE_RENAMES = {
    'hp_data_source': 'data_sources',
    'hp_domain': 'domains',
    'hp_topic': 'topics',
    'hp_news': 'articles',
    'sys_prompt_version': 'prompt_versions',
    'act_domain_topic_actions': 'domain_topic_rules',
    'news_prompt_usage': 'prompt_usages',
    'news_embedding': 'embeddings',
}

# Public business names omit the redundant application-wide pipeline prefix.
APPLICATION_TABLE_RENAMES = {
    'pipeline_content_review_events': 'content_review_events',
    'pipeline_duplicate_group_events': 'duplicate_group_events',
    'pipeline_duplicate_groups': 'duplicate_groups',
    'pipeline_duplicate_members': 'duplicate_members',
    'pipeline_model_call_audits': 'model_calls',
    'pipeline_model_route_usage': 'model_route_usage',
    'pipeline_model_routes': 'model_routes',
    'pipeline_prompt_versions': 'prompt_versions',
    'pipeline_quality_issue_events': 'quality_issue_events',
    'pipeline_quality_issues': 'quality_issues',
    'pipeline_template_versions': 'template_versions',
}

APPLICATION_INTERMEDIATE_RENAMES = {
    'review_events': 'content_review_events',
    'duplicate_events': 'duplicate_group_events',
    'route_usage': 'model_route_usage',
    'quality_events': 'quality_issue_events',
}

SCHEDULER_TABLE_COMMENT = 'APScheduler 持久化任务存储表，由若依调度器维护，不是业务任务执行记录'
SCHEDULER_COLUMN_COMMENTS = {
    'id': '调度任务唯一标识，由 APScheduler 分配，与 sys_job 的业务任务编号不是同一字段',
    'next_run_time': '下次调度的 Unix 时间戳，单位秒，空值表示任务暂停或尚无下次执行时间',
    'job_state': 'APScheduler 序列化任务状态，二进制 Pickle 数据，仅由可信调度器写入和反序列化',
}


def annotate_scheduler_table(table: Table) -> None:
    """Keep newly auto-created scheduler tables documented without extra DDL."""
    if set(table.columns.keys()) != set(SCHEDULER_COLUMN_COMMENTS):
        raise ValueError('APScheduler 表字段已变化，请先补齐字段注释')
    table.comment = SCHEDULER_TABLE_COMMENT
    for name, comment in SCHEDULER_COLUMN_COMMENTS.items():
        table.c[name].comment = comment
