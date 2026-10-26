from app.research.schemas.manuscript import ManuscriptGenerateModel
from app.research.services.manuscript import ManuscriptApiService
from exceptions.exception import ServiceException

EXPECTED_TITLE_COUNT = 5


def test_manuscript_payload_rejects_blank_topic() -> None:
    body = ManuscriptGenerateModel(topic='   ')

    try:
        ManuscriptApiService.to_research_payload(body)
    except ServiceException as exc:
        assert exc.message == '论文题目不能为空'
    else:  # pragma: no cover - keeps the assertion explicit for this guard
        raise AssertionError('blank manuscript topic should be rejected')


def test_manuscript_payload_uses_persistent_research_task_contract() -> None:
    body = ManuscriptGenerateModel(
        topic='管道本体应力监测技术研究',
        description='围绕长输管道本体应力监测、磁各向异性传感和现场验证形成论文草稿。',
        keywords=['应力监测', '磁各向异性', '现场验证'],
        provided_references=['张三等. 管道应力监测研究进展[J]. 油气储运, 2025.'],
        custom_options={'generate_figures': True},
    )

    payload = ManuscriptApiService.to_research_payload(body)

    assert payload.title == '管道本体应力监测技术研究'
    assert payload.report_type == 'technology-route'
    assert payload.selected_item_ids == []
    assert payload.options['manualReferences'] == ['张三等. 管道应力监测研究进展[J]. 油气储运, 2025.']
    assert payload.options['manuscript'] is True
    assert payload.diagram is True
    assert payload.requirements.startswith('围绕长输管道')


def test_custom_outline_is_normalized_for_research_report_builder() -> None:
    body = ManuscriptGenerateModel(
        topic='管网数据治理研究',
        custom_outline={
            'sections': [
                {'heading': '数据质量控制', 'level': 1, 'description': '说明校验方法。', 'words': 800},
                {'heading': '', 'level': 1},
            ]
        },
    )

    payload = ManuscriptApiService.to_research_payload(body)

    assert payload.outline == [
        {'title': '数据质量控制', 'level': 1, 'words': 800, 'description': '说明校验方法。'}
    ]


def test_suggest_titles_uses_keywords_and_domain_language() -> None:
    titles = ManuscriptApiService.suggest_titles(
        description='研究管道缺陷识别与多元检测数据融合方法',
        keywords=['缺陷识别', '数据融合'],
    )

    assert len(titles) == EXPECTED_TITLE_COUNT
    assert any('缺陷识别' in title for title in titles)
    assert all(title.endswith(('研究', '方法', '综述')) for title in titles)
