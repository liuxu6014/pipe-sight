"""Run automatic dispatch against real SQLite selection queries, never a model API."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from test_digest_schedule_generation_guard import dispatch_fixture, setup_template
from test_digest_selection_policy import canonical_content
from test_research_simplified_20261025 import AsyncMemory
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network

env = memory_env
db = memory_db
no_external_network = offline_network


@pytest.mark.asyncio
@pytest.mark.parametrize('frequency', ['daily', 'weekly', 'monthly'])
@pytest.mark.parametrize('shape', ['canonical', 'legacy_options', 'generation_fallback'])
@pytest.mark.parametrize('has_match', [True, False])
async def test_dispatch_uses_only_matching_period_source_category_and_any_keyword(
    env, db, monkeypatch, frequency, shape, has_match
):
    await setup_template(env, db)
    base, source, category, article = canonical_content(env, monkeypatch)
    engine = create_engine('sqlite:///:memory:')
    base.metadata.create_all(engine)
    when = datetime(2026, 9, 15) if frequency == 'monthly' else datetime(2026, 10, 24)
    words = ['未命中词', '管道', '腐蚀'] if has_match else ['未命中词']
    options = {'sources': ['新闻网站'], 'directions': ['后台类别']}
    selection = {'limit': 50}
    generation = {}
    if shape == 'canonical':
        selection.update(keywords=words, source_types=['website'], category_names=['后台类别'])
    elif shape == 'legacy_options':
        selection.update(keywords=words, options=options)
    else:
        generation = {'keywords': words, 'options': options}
    real_candidates = env.repo.ResearchDao.digest_candidates
    try:
        with Session(engine) as session:
            session.add_all([source(id=1, type='website'), source(id=2, type='wechat')])
            session.add_all([category(id=801, name='后台类别'), category(id=802, name='其他类别')])
            for ident, title, body, source_id, category_id, published in [
                (1, '管道检测', '实际正文', 1, 801, when),
                (2, '其他题名', '腐蚀防护', 1, 801, when),
                (3, '管道错误类别', '实际正文', 1, 802, when),
                (4, '管道错误来源', '实际正文', 2, 801, when),
                (5, '无关文章', '无关正文', 1, 801, when),
                (6, '管道过期文章', '实际正文', 1, 801, datetime(2020, 1, 1)),
                (7, '管道空正文', '', 1, 801, when),
                (8, '管道检测', '重复标题正文', 1, 801, when),
            ]:
                session.add(article(id=ident, title=title, content=body, source_id=source_id,
                                    category_id=category_id, published_at=published))
            session.commit()

            async def select_real_content(unused_db, start, end, config):
                return await real_candidates(AsyncMemory(session), start, end, config)

            result, row, enqueue, query, _ = await dispatch_fixture(
                env, db, monkeypatch, generation, selection_config=selection,
                candidate_loader=select_real_content, frequency=frequency,
            )
            assert result['failed'] == 0
            assert query.await_args.args[-1]['keywords'] == words
            if has_match:
                assert result['queued'] == 1
                payload = enqueue.await_args.kwargs['payload']
                assert payload['selected_item_ids'] == ['1', '2']
                assert payload['keywords'] == words
                assert payload['selection_strategy']['candidate_count'] == 2
            else:
                assert result['no_data'] == 1 and result['queued'] == 0
                enqueue.assert_not_awaited()
    finally:
        engine.dispose()


@pytest.mark.parametrize('config', [
    {'keywords': '管道'}, {'category_names': '后台类别'},
    {'source_types': ['未知来源']}, {'source_types': []},
    {'keywords': ['词'] * 21}, {'options': {'directions': '后台类别'}},
])
def test_invalid_saved_filters_fail_closed_instead_of_selecting_everything(env, config):
    with pytest.raises(env.exc):
        env.schedules.DigestScheduleService._selection_config(config)


@pytest.mark.asyncio
async def test_dispatch_with_invalid_saved_filters_never_queries_or_enqueues(env, db, monkeypatch):
    await setup_template(env, db)
    result, row, enqueue, query, before = await dispatch_fixture(
        env, db, monkeypatch, {}, selection_config={'keywords': '管道', 'limit': 50},
    )
    assert result['failed'] == 1 and result['queued'] == 0
    query.assert_not_awaited()
    enqueue.assert_not_awaited()
    assert env.repo.ResearchDao.aware(row.next_run_at) == before
