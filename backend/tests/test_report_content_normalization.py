"""The real provider's JSON is an article document, never a JSON paragraph."""

import json

import pytest

from app.research.services.report_content import normalize_generated_report, sections_from_markdown


def structured():
    return json.dumps({'title': '报告', '说明': '仅依据所选资料。', 'sections': [
        {'id': 1, 'title': '生产需求及技术问题', 'content': '已有证据[资料18]。\n\n拟开展的研究，待验证。'},
        {'id': 2, 'title': '经费需求', 'content': '预算待论证，不虚构金额。'},
    ], 'references': [{'id': '999', 'title': '模型编造的文献'}]}, ensure_ascii=False)


@pytest.mark.parametrize('fenced', [False, True])
def test_structured_output_is_real_headings_paragraphs_and_trusted_references(fenced):
    raw = structured()
    if fenced:
        raw = '```json\n' + raw + '\n```'
    materials = [{'id': '18', 'type': 'article', 'title': '真实来源', 'source': {
        'url': 'https://example.invalid/real', 'published_at': '2025-04-09T16:00:00+00:00'}}]
    result = normalize_generated_report(raw, materials)
    assert result['content'].startswith('## 编制说明\n\n仅依据所选资料。')
    assert '## 生产需求及技术问题\n\n已有证据[1]。\n\n拟开展的研究，待验证。' in result['content']
    assert '\\n' not in result['content'] and '"sections"' not in result['content']
    assert [s['title'] for s in result['sections']] == ['编制说明', '生产需求及技术问题', '经费需求', '参考资料']
    assert '[1]' in result['content'] and '[资料18]' not in result['content'] and '2025-04-10' in result['content']
    assert 'https://example.invalid/real' in result['content']
    assert '模型编造的文献' not in result['content'] and '999' not in result['content']
    assert result['sections'] == sections_from_markdown(result['content'])


def test_plain_markdown_is_not_rewritten_or_wrapped_in_json():
    text = '## 研究背景\n\n真实正文。\n\n## 经费需求\n\n待补充。'
    result = normalize_generated_report(text)
    assert result['content'] == text
    assert [s['title'] for s in result['sections']] == ['研究背景', '经费需求']
    assert normalize_generated_report(text, [])['content'] == text


def test_markdown_preface_and_numbered_headings_survive_without_number_growth():
    text = '# 报告标题\n\n导言正文。\n\n## 1. 技术现状\n\n已有正文。\n\n## 2. 经费需求\n\n待论证。'
    sections = sections_from_markdown(text)
    assert [s['title'] for s in sections] == ['引言', '技术现状', '经费需求']
    assert sections[0]['content'] == '导言正文。'
    assert sections[1]['content'] == '已有正文。'


def test_headings_inside_code_fences_do_not_create_spurious_chapters():
    text = '## 技术方案\n\n```text\n## 只是样例数据\n```\n\n## 经费需求\n\n待补充。'
    sections = sections_from_markdown(text)
    assert len(sections) == 2 and '## 只是样例数据' in sections[0]['content']


@pytest.mark.parametrize('payload', [
    '{"sections":', '{"sections": []}', '{"sections": [{"title":"空章","content":""}]}',
    '{"sections": [{"title":"一\\n二","content":"不能注入标题"}]}',
    '{"sections": [{"title":"一","content":{"nested":"不能展示对象"}}]}',
    '{"arbitrary":"不能把结构对象直接冒充文章"}',
])
def test_invalid_structured_result_fails_explicitly_instead_of_persisting_json(payload):
    with pytest.raises(ValueError):
        normalize_generated_report(payload)


def test_structured_single_content_wrapper_is_unwrapped():
    result = normalize_generated_report(json.dumps({'content': '## 研究内容\n\n正文。'}))
    assert result['content'] == '## 研究内容\n\n正文。'


def test_normalized_article_is_idempotent_and_has_one_reference_section():
    materials = [{'id': '26', 'type': 'paper', 'title': '真实论文', 'source': {'published_date':'2024-03'}}]
    first = normalize_generated_report(structured(), materials)
    second = normalize_generated_report(first['content'], materials)
    assert first == second and second['content'].count('## 参考资料') == 1


@pytest.mark.parametrize('structured_output', [False, True])
def test_new_reports_persist_sentence_end_citations_without_notes_or_duplicates(structured_output):
    body = '[资料26]研究指出检测可行[资料26]（论文摘要，2024-03），仍需验证。另一项结论[资料26]。'
    raw = (json.dumps({'sections': [{'title': '研究内容', 'content': body}]}, ensure_ascii=False)
           if structured_output else '## 研究内容\n\n' + body + '\n\n## 参考资料\n\n[资料26] 论文；2024-03')
    materials = [{'id': '26', 'type': 'paper', 'title': '真实论文', 'source': {'published_date': '2024-03'}}]
    result = normalize_generated_report(raw, materials)
    assert result['sections'][0]['content'] == '研究指出检测可行，仍需验证[1]。另一项结论[1]。'
    assert '[1] ' in result['sections'][-1]['content'] and '2024-03' in result['sections'][-1]['content']
    assert normalize_generated_report(result['content'], materials) == result


def test_citation_cleanup_preserves_reference_rows_markdown_links_and_code():
    raw = ('## 正文\n\n研究[1]表明可行[1]，有待验证。\n\n'
           '示例 `[1]` 与 [1](https://example.org) 不移动。\n\n'
           '```text\n示例[1]不移动。\n```\n\n'
           '## 参考文献\n\n[1] 论文（论文摘要，2024-03）\n\n'
           '## 附录\n\n[1]研究需要验证。')
    result = normalize_generated_report(raw)
    assert '研究表明可行，有待验证[1]。' in result['content']
    assert '示例 `[1]` 与 [1](https://example.org) 不移动。' in result['content']
    assert '```text\n示例[1]不移动。\n```' in result['content']
    assert '[1] 论文（论文摘要，2024-03）' in result['content']
    assert result['sections'][-1]['content'] == '研究需要验证[1]。'
