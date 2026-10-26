from app.intelligence.services.data_processing import PipelineDataProcessingService

MIN_RELEVANCE_SCORE = 70
PROMPT_VERSION = 3


def test_normalizes_text_and_removes_tracking_parameters_from_urls() -> None:
    service = PipelineDataProcessingService

    assert service.normalize_text('<p>　管道&nbsp;监测</p>') == '管道 监测'
    assert (
        service.canonicalize_url('HTTPS://Example.COM:443/news?a=2&utm_source=wechat#section')
        == 'https://example.com/news?a=2'
    )


def test_simhash_recognizes_near_duplicate_text() -> None:
    service = PipelineDataProcessingService
    left = service.simhash('国家管网发布管道完整性监测技术进展和应用情况')
    right = service.simhash('国家管网发布管道完整性监测技术进展与应用情况')
    different = service.simhash('春季园林绿化项目完成验收并投入使用')

    threshold = service.SIMHASH_DISTANCE_THRESHOLD
    assert service.simhash_distance(left, right) <= threshold
    assert service.simhash_distance(left, different) > threshold


def test_process_record_returns_explainable_quality_and_classification() -> None:
    result = PipelineDataProcessingService.process_record(
        {
            'title': '国家管网完成管道完整性监测技术验证',
            'url': 'https://example.com/news?id=1&utm_medium=feed',
            'summary': '<p>介绍应力监测和泄漏预警的工程应用。</p>',
            'body': '管道完整性管理、腐蚀防护和监测预警技术在油气管网工程中完成验证。' * 20,
            'published_time': '2026-10-01',
        },
        source_type='news',
        source_name='国家管网集团要闻',
        filter_prompt={'promptKey': 'data-filter', 'versionNo': PROMPT_VERSION},
    )

    assert result['keep'] is True
    assert result['status'] == 'accepted'
    assert result['canonical_url'] == 'https://example.com/news?id=1'
    assert result['score'] >= MIN_RELEVANCE_SCORE
    assert '管道完整性' in result['tags']
    assert '监测预警' in result['tags']
    assert result['quality']['status'] == 'pass'
    assert result['processing']['filter']['mode'] == 'rule-based'
    assert result['processing']['filter']['promptVersionNo'] == PROMPT_VERSION


def test_process_record_executes_filter_prompt_contract_with_traceable_fallback() -> None:
    result = PipelineDataProcessingService.process_record(
        {
            'title': '国家管网完成管道完整性监测技术验证',
            'url': 'https://example.com/prompt-contract',
            'summary': '管网监测与泄漏预警技术应用。',
            'body': '管道完整性管理和监测预警技术在油气管网工程中完成验证。' * 12,
            'published_time': '2026-10-01',
        },
        source_type='news',
        source_name='国家管网集团要闻',
        filter_prompt={
            'promptId': 'prompt-data-filter-v3',
            'promptKey': 'data-filter',
            'versionNo': PROMPT_VERSION,
            'executionMode': 'external-handoff',
            'systemPrompt': '输出 keep、score、reason、category、keywords。',
            'userPrompt': '标题：{{title}} 正文：{{body}}',
            'modelRoute': {
                'routeId': 'route-data-filter',
                'versionNo': 2,
                'primary': {'id': 1, 'provider': 'DeepSeek', 'code': 'deepseek-chat'},
                'fallback': {'id': 2, 'provider': 'DeepSeek', 'code': 'deepseek-reasoner'},
                'timeoutSeconds': 20,
                'maxTokens': 512,
                'temperature': 0.1,
                'dailyLimit': 100,
            },
        },
    )

    filter_result = result['processing']['filter']
    assert filter_result['schema'] == 'pipesight-filter-v1'
    assert filter_result['promptApplied'] is True
    assert filter_result['executionMode'] == 'rule-based-fallback'
    assert filter_result['decision']['keep'] is True
    assert filter_result['decision']['score'] == result['score']
    assert filter_result['decision']['category'] == result['category']
    assert filter_result['fallback']['reason']
    assert filter_result['input']['title'] == result['title']
    assert filter_result['promptSnapshot']['promptId'] == 'prompt-data-filter-v3'
    assert filter_result['promptSnapshot']['executionMode'] == 'external-handoff'
    assert filter_result['promptSnapshot']['modelRoute']['primary']['code'] == 'deepseek-chat'
    assert filter_result['promptSnapshot']['modelRoute']['fallback']['code'] == 'deepseek-reasoner'


def test_process_record_rejects_invalid_records_with_reason() -> None:
    result = PipelineDataProcessingService.process_record(
        {'title': '无效', 'url': '', 'summary': '', 'body': ''},
        source_type='news',
        source_name='测试来源',
    )

    assert result['keep'] is False
    assert result['status'] == 'rejected'
    assert '缺少规范化地址' in result['processing']['quality']['issues']


def test_process_record_uses_explicit_relevance_threshold() -> None:
    result = PipelineDataProcessingService.process_record(
        {
            'title': '一般行业通知',
            'url': 'https://example.com/notice',
            'summary': '这是一段长度足够但与管网科技主题无关的普通通知内容。' * 3,
            'published_time': '2026-10-01',
        },
        source_type='news',
        source_name='测试来源',
    )

    assert result['score'] < PipelineDataProcessingService.MIN_RELEVANCE_SCORE
    assert result['keep'] is False
    assert '未命中管网相关性规则' in result['processing']['quality']['issues']
    assert (
        result['processing']['filter']['rulePolicy']['minimumRelevanceScore']
        == PipelineDataProcessingService.MIN_RELEVANCE_SCORE
    )
