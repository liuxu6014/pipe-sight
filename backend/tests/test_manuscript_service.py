import pytest

from module_manuscript.service.manuscript_service import ManuscriptService

EXPECTED_TITLE_COUNT = 5


def setup_function() -> None:
    ManuscriptService.reset()


def test_generate_manuscript_job_builds_completed_pipeline_draft() -> None:
    job = ManuscriptService.generate_manuscript(
        topic='管道本体应力监测技术研究',
        description='围绕长输管道本体应力监测、磁各向异性传感和现场验证形成论文草稿。',
        keywords=['应力监测', '磁各向异性', '现场验证'],
        provided_references=['张三等. 管道应力监测研究进展[J]. 油气储运, 2025.'],
    )

    assert job['job_id'].startswith('ms-')
    assert job['status'] == 'completed'
    assert [stage['key'] for stage in job['stages']] == ['researching', 'outlining', 'writing', 'exporting']
    assert '# 管道本体应力监测技术研究' in job['content']
    assert '## 摘要' in job['content']
    assert '应力监测' in job['content']
    assert '张三等. 管道应力监测研究进展' in job['content']


def test_list_manuscripts_filters_keyword_and_export_returns_markdown_payload() -> None:
    ManuscriptService.generate_manuscript(
        topic='管道本体应力监测技术研究',
        description='磁各向异性传感。',
        keywords=['应力监测'],
    )
    other = ManuscriptService.generate_manuscript(
        topic='站场设备数字化运维综述',
        description='设备状态评价。',
        keywords=['数字化运维'],
    )

    result = ManuscriptService.list_manuscripts(keyword='运维')
    exported = ManuscriptService.export_manuscript(other['job_id'])

    assert result['total'] == 1
    assert result['rows'][0]['job_id'] == other['job_id']
    assert exported['file_name'] == '站场设备数字化运维综述.md'
    assert exported['content'].startswith('# 站场设备数字化运维综述')


def test_generate_manuscript_requires_topic() -> None:
    with pytest.raises(ValueError, match='topic is required'):
        ManuscriptService.generate_manuscript(topic='  ', description='empty topic')


def test_suggest_titles_uses_keywords_and_domain_language() -> None:
    titles = ManuscriptService.suggest_titles(
        description='研究管道缺陷识别与多元检测数据融合方法',
        keywords=['缺陷识别', '数据融合'],
    )

    assert len(titles) == EXPECTED_TITLE_COUNT
    assert any('缺陷识别' in title for title in titles)
    assert all(title.endswith(('研究', '方法', '综述')) for title in titles)
