"""Reject pre-migration ID types even when every table/column name matches."""

from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, Column, ForeignKey, MetaData, String, Table
from sqlalchemy.dialects import postgresql

from config import get_db


@pytest.mark.parametrize('wrong', [('reports', 'id'), ('report_versions', 'report_id')])
def test_startup_rejects_varchar_business_primary_or_foreign_key(monkeypatch, wrong):
    metadata = MetaData()
    Table('reports', metadata, Column('id', BigInteger, primary_key=True))
    Table(
        'report_versions',
        metadata,
        Column('id', BigInteger, primary_key=True),
        Column('report_id', BigInteger, ForeignKey('reports.id')),
    )

    def columns(name, **kwargs):
        return [
            {'name': column.name, 'type': String(64) if (name, column.name) == wrong else BigInteger()}
            for column in metadata.tables[name].columns
        ]

    monkeypatch.setattr(get_db, 'Base', SimpleNamespace(metadata=metadata))
    monkeypatch.setattr(
        get_db, 'inspect', lambda *args: SimpleNamespace(has_table=lambda *a, **kw: True, get_columns=columns)
    )
    with pytest.raises(RuntimeError, match=wrong[0] + '.' + wrong[1]):
        get_db.validate_schema(SimpleNamespace(dialect=postgresql.dialect()))
