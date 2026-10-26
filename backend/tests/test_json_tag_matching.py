"""Category filters now use one FK; JSON tag storage has retired."""

import sqlite3

import pytest
from sqlalchemy.dialects import sqlite

from app.intelligence.models.content import PipelineArticle, PipelinePaper
from app.intelligence.repositories.content_repository import ContentDao


@pytest.mark.parametrize('model', [PipelineArticle, PipelinePaper])
@pytest.mark.parametrize('category', ['智能巡检', '智能%巡检', '智能_巡检', r'智能\巡检', '智能"巡检', '智能🚀巡检'])
def test_category_name_is_exact_not_json_or_wildcard(
    model: type[PipelineArticle] | type[PipelinePaper], category: str
) -> None:
    query, _, _ = ContentDao.query(model, category_id=category)
    query = query.with_only_columns(model.id, maintain_column_froms=True)
    compiled = query.compile(dialect=sqlite.dialect())
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE categories (id INTEGER, name TEXT)')
        db.execute('INSERT INTO categories VALUES (?, ?)', (501, category))
        db.execute('INSERT INTO categories VALUES (?, ?)', (502, '智能普通巡检'))
        db.execute('CREATE TABLE data_sources (id INTEGER, type TEXT)')
        db.execute("INSERT INTO data_sources VALUES (101, 'wechat')")
        db.execute(f'CREATE TABLE {model.__tablename__} (id INTEGER, category_id INTEGER, source_id INTEGER)')
        db.executemany(
            f'INSERT INTO {model.__tablename__} VALUES (?, ?, ?)',
            [
                (1001, 501, 101),
                (1002, 502, 101),
                (1003, None, 101),
            ],
        )
        params = tuple(compiled.params[name] for name in compiled.positiontup)
        assert db.execute(str(compiled), params).fetchall() == [(1001,)]


@pytest.mark.parametrize('model', [PipelineArticle, PipelinePaper])
def test_multiple_selected_categories_are_alternatives_for_a_single_fk(
    model: type[PipelineArticle] | type[PipelinePaper],
) -> None:
    query, _, _ = ContentDao.query(model, tags=['智能巡检', '管道安全'])
    sql = str(query.compile(compile_kwargs={'literal_binds': True}))
    assert "categories.name IN ('智能巡检', '管道安全')" in sql
    assert f'{model.__tablename__}.category_id = categories.id' in sql
    assert f'{model.__tablename__}.tags' not in sql
    assert f'{model.__tablename__}.keywords' not in sql
    (fk,) = model.__table__.c.category_id.foreign_keys
    assert fk.target_fullname == 'categories.id' and fk.ondelete == 'RESTRICT'
    assert not model.__table__.c.category_id.unique
