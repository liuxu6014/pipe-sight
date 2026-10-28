"""New manuscripts share delivery rules without rewriting existing reports."""
import pytest

from app.research.services.writing_rules import template_writing_prompt
from app.research.services.report_content import normalize_generated_report


@pytest.mark.parametrize('kind', ['research', 'daily', 'weekly', 'monthly'])
def test_delivery_rules_cover_research_and_all_digest_cadences(kind):
    prompt = template_writing_prompt({'purpose': 'research' if kind == 'research' else 'digest', 'prompt': '管理员要求'}, kind)
    assert '管理员要求' in prompt
    assert '交付文稿规范' in prompt
    assert '自然段' in prompt
    assert '内部参数' in prompt
    assert '参考资料由系统' in prompt


def test_new_manuscript_removes_parameter_cover_and_rebuilds_authoritative_references():
    raw = ('# 行业进展\n\n报告周期：2026-10-26\n研究方向：油气管网\n关键词：管道、腐蚀\n'
           '条目数：2（不足3条）\n\n## 技术进展\n\n检测技术进入验证阶段[article:18]。\n\n'
           '## 来源清单\n\n[1] 模型编造标题；https://wrong.invalid\n\n'
           '## 参考文献\n\n重复的来源。')
    materials = [{'id': '18', 'type': 'article', 'title': '真实新闻',
                  'source': {'url': 'https://example.org/real', 'published_at': '2026-10-26 08:00:00'}}]
    result = normalize_generated_report(raw, materials, delivery=True)
    assert [section['title'] for section in result['sections']] == ['技术进展', '参考资料']
    assert result['sections'][0]['content'] == '检测技术进入验证阶段[1]。'
    assert 'https://example.org/real' in result['content'] and '真实新闻' in result['content']
    assert 'wrong.invalid' not in result['content'] and '条目数' not in result['content']
    assert normalize_generated_report(result['content'], materials, delivery=True) == result


def test_delivery_preserves_real_narrative_and_evidence_limitations():
    text = '## 技术分析\n\n关键词提取有助于信息检索。公开摘要尚未披露长期运行数据，不能据此判断寿命。'
    result = normalize_generated_report(text, delivery=True)
    assert result['content'] == text


def test_legacy_normalization_does_not_remove_existing_cover_text():
    text = '研究方向：历史范围\n\n## 研究内容\n\n原有正文。'
    assert normalize_generated_report(text)['sections'][0]['content'] == '研究方向：历史范围'


@pytest.mark.parametrize('level', ['#', '##', '###', '####'])
def test_delivery_replaces_reference_sections_at_any_heading_level(level):
    materials = [{'id': '18', 'type': 'article', 'title': '真实新闻', 'source': {}}]
    raw = f'## 分析\n\n真实论述[article:18]。\n\n{level} 参考文献\n\n模型虚构来源'
    result = normalize_generated_report(raw, materials, delivery=True)
    assert '模型虚构来源' not in result['content']
    assert result['content'].count('参考资料') == 1
    assert '真实论述[1]。' in result['content']


@pytest.mark.parametrize('body', [
    '## 分析\n\n结论[99]。',
    '## 分析\n\n结论[paper:999]。',
    '## 分析\n\n没有引用的事实性文稿。',
    '## 研究目标\n\n## 研究内容\n\n实际正文[1]。',
    '## 分析\n\n```json\n{"正文":"不完整"}',
])
def test_generated_delivery_validation_rejects_invalid_manuscripts(body):
    from app.research.services.report_content import validate_generated_article
    materials = [{'id': '18', 'type': 'article', 'title': '真实新闻', 'source': {}}]
    article = normalize_generated_report(body, materials, delivery=True)
    with pytest.raises(ValueError, match='文稿检查未通过'):
        validate_generated_article(article['content'], materials)


def test_delivery_validation_preserves_proposals_and_does_not_require_every_source_to_be_cited():
    from app.research.services.report_content import validate_generated_article
    materials = [{'id': '18', 'type': 'article'}, {'id': '24', 'type': 'paper'}]
    validate_generated_article('## 研究背景\n\n已报道事实[1]。\n\n## 研究建议\n\n拟开展验证。', materials)


def test_delivery_validation_accepts_parent_chapters_with_subsection_prose():
    from app.research.services.report_content import validate_generated_article
    validate_generated_article('## 研究内容\n\n### 数据条件\n\n需确认数据许可[1]。\n\n### 验证方法\n\n拟对照复核。',
                               [{'id': '18', 'type': 'article'}])


def test_bibliography_includes_available_authors_and_real_publisher():
    materials = [{'id': '24', 'type': 'paper', 'title': '论文',
                  'source': {'authors': '作者甲', 'journal': '期刊甲'}},
                 {'id': '18', 'type': 'article', 'title': '新闻',
                  'source': {'publisher': '新华网'}}]
    content = normalize_generated_report('## 分析\n\n事实[1]。', materials, delivery=True)['content']
    assert '作者甲' in content and '新华网' in content
