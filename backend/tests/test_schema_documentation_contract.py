"""Documentation safeguards for automatically created infrastructure tables."""

import pytest
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from config.schema_documentation import (
    SCHEDULER_COLUMN_COMMENTS,
    SCHEDULER_TABLE_COMMENT,
    annotate_scheduler_table,
)


def test_scheduler_new_table_carries_every_comment() -> None:
    store = SQLAlchemyJobStore(url='sqlite://')
    annotate_scheduler_table(store.jobs_t)
    assert store.jobs_t.comment == SCHEDULER_TABLE_COMMENT
    assert {column.name: column.comment for column in store.jobs_t.c} == SCHEDULER_COLUMN_COMMENTS
    assert 'apscheduler_jobs' in str(CreateTable(store.jobs_t).compile(dialect=postgresql.dialect()))
    store.engine.dispose()


def test_scheduler_unknown_column_fails_before_creating_undocumented_table() -> None:
    table = Table('changed_jobs', MetaData(), Column('new_field', String))
    with pytest.raises(ValueError, match='字段已变化'):
        annotate_scheduler_table(table)
