import json
from types import SimpleNamespace

import pytest

from app.intelligence.services.entities import EntityExtractionService


def model(identity=1, *, enabled=True, capabilities=None):
    return SimpleNamespace(
        id=identity,
        is_enabled=enabled,
        capabilities=capabilities or ['text_generate'],
        provider='compatible',
        code='fixture',
        base_url='https://example.invalid',
        parameters={},
    )


class Database:
    def __init__(self, models):
        self.models = models

    async def execute(self, statement):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [m for m in self.models if m.is_enabled]))

    async def get(self, entity, identity):
        return next((m for m in self.models if m.id == identity), None)


@pytest.mark.asyncio
async def test_unbound_source_uses_the_only_enabled_text_model_and_preserves_all_six_types():
    calls = []
    expected = [
        {'type': '地点', 'name': '深圳'},
        {'type': '时间', 'name': '12月3日'},
        {'type': '政策', 'name': '绿色运输规划'},
        {'type': '人物', 'name': '张某'},
        {'type': '机构', 'name': '研究中心'},
        {'type': '技术', 'name': '超声检测'},
    ]

    async def gateway(db, snapshot, **kwargs):
        calls.append(snapshot['id'])
        return json.dumps({'entities': expected}, ensure_ascii=False)

    result = await EntityExtractionService.extract(
        Database([model(), model(2, capabilities=['image_generate']), model(3, enabled=False)]),
        title='研究中心在深圳开展超声检测',
        content='12月3日，张某介绍绿色运输规划。',
        gateway=gateway,
    )
    assert calls == [1]
    assert result == expected


@pytest.mark.asyncio
async def test_explicit_disabled_model_does_not_silently_switch_providers():
    async def forbidden(*args, **kwargs):
        raise AssertionError('must not call a fallback model')

    assert (
        await EntityExtractionService.extract(
            Database([model(), model(2, enabled=False)]),
            title='新闻',
            content='正文',
            model_id=2,
            gateway=forbidden,
        )
        is None
    )


@pytest.mark.asyncio
async def test_ambiguous_or_missing_default_requires_an_explicit_binding():
    assert await EntityExtractionService.resolve_model(Database([])) is None
    db = Database([model(1), model(2)])
    assert await EntityExtractionService.resolve_model(db) is None
    assert (await EntityExtractionService.resolve_model(db, 2)).id == 2


@pytest.mark.asyncio
async def test_only_grounded_entities_survive_fences_aliases_and_duplicates():
    async def gateway(*args, **kwargs):
        return (
            '```json\n'
            + json.dumps(
                {
                    'entities': [
                        {'type': '地点', 'name': '深圳'},
                        {'type': '地点', 'name': '北京'},
                        {'type': '人', 'name': '张某'},
                        {'type': '人物', 'name': ' 张某 '},
                        {'type': '时间', 'name': '2026年12月3日'},
                        {'type': '机构', 'name': '国家管网'},
                        {'type': '未知', 'name': '深圳'},
                    ]
                },
                ensure_ascii=False,
            )
            + '\n```'
        )

    assert await EntityExtractionService.extract(
        Database([model()]),
        title='深圳开展试验',
        content='张某在12月3日介绍国家管网。',
        gateway=gateway,
    ) == [{'type': '地点', 'name': '深圳'}, {'type': '人物', 'name': '张某'}, {'type': '机构', 'name': '国家管网'}]


@pytest.mark.asyncio
async def test_valid_empty_result_is_distinct_from_unavailable_or_malformed_output():
    async def empty(*args, **kwargs):
        return '{"entities":[]}'

    async def malformed(*args, **kwargs):
        return 'invalid'

    db = Database([model()])
    assert await EntityExtractionService.extract(db, title='新闻', content='正文', gateway=empty) == []
    assert await EntityExtractionService.extract(db, title='新闻', content='正文', gateway=malformed) is None


@pytest.mark.asyncio
async def test_collector_delegates_unbound_sources_instead_of_skipping_extraction(monkeypatch):
    from app.intelligence.services import collection

    calls = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def commit(self):
            pass

    async def extract(db, **kwargs):
        calls.append(kwargs)
        return {'entities': []}

    monkeypatch.setattr(collection, 'classification_session_factory', lambda db: Session)
    monkeypatch.setattr(EntityExtractionService, 'enrich', extract)
    result = await collection.PipelineCollectionService.enrich_records(
        object(),
        [{'title': '新闻', 'content': '正文'}, {'title': ''}],
        None,
    )
    assert result == [{'entities': []}, None]
    assert len(calls) == 1 and calls[0]['model_id'] is None


@pytest.mark.asyncio
async def test_full_text_inventory_is_rejected_instead_of_taking_the_first_six():
    async def gateway(*args, **kwargs):
        return json.dumps({'entities': [{'type': '技术', 'name': f'方法{i}'} for i in range(8)]})

    assert (
        await EntityExtractionService.extract(
            Database([model()]), title='核心研究', content='、'.join(f'方法{i}' for i in range(8)), gateway=gateway
        )
        is None
    )


@pytest.mark.asyncio
async def test_many_background_dates_are_rejected_even_below_total_limit():
    async def gateway(*args, **kwargs):
        return json.dumps({'entities': [{'type': '时间', 'name': year} for year in ['1988年', '2008年', '2019年']]})

    assert (
        await EntityExtractionService.extract(
            Database([model()]), title='检测合作', content='1988年、2008年、2019年是公司历史。', gateway=gateway
        )
        is None
    )


@pytest.mark.asyncio
async def test_paper_entities_use_abstract_evidence_without_inventing_author_affiliation():
    calls = []

    async def gateway(db, snapshot, **kwargs):
        calls.append(kwargs)
        return json.dumps(
            {
                'entities': [
                    {'type': '技术', 'name': '超声导波'},
                    {'type': '机构', 'name': '假设研究院'},
                ],
                'summary': '不应改写论文摘要',
            }
        )

    result = await EntityExtractionService.enrich(
        Database([model()]),
        title='管道腐蚀检测综述',
        content='介绍超声导波用于管道腐蚀检测。',
        kind='paper',
        gateway=gateway,
    )
    assert result == {'entities': [{'type': '技术', 'name': '超声导波'}]}
    assert json.loads(calls[0]['prompt'])['sourceType'] == 'paper'
    assert '不按作者姓名猜测任职机构' in calls[0]['system_prompt']


@pytest.mark.asyncio
async def test_collector_paper_processing_passes_only_abstract_not_full_body(monkeypatch):
    from app.intelligence.services import collection

    calls = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def commit(self):
            pass

    async def enrich(db, **kwargs):
        calls.append(kwargs)
        return {'entities': []}

    monkeypatch.setattr(collection, 'classification_session_factory', lambda db: Session)
    monkeypatch.setattr(EntityExtractionService, 'enrich', enrich)
    await collection.PipelineCollectionService.enrich_records(
        object(), [{'title': '论文', 'content': '不得使用的全文', 'abstract': '原始摘要'}], None, kind='paper'
    )
    assert calls[0]['content'] == '原始摘要' and calls[0]['kind'] == 'paper'
